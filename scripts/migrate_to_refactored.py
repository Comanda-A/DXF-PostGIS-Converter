# -*- coding: utf-8 -*-
"""
Скрипт миграции на рефакторированную версию.

Выполняет:
1. Резервное копирование старых файлов
2. Переключение на новую версию
3. Возможность отката

Использование:
    python scripts/migrate_to_refactored.py --backup    # Создать бэкап
    python scripts/migrate_to_refactored.py --migrate   # Переключить на новую версию
    python scripts/migrate_to_refactored.py --rollback  # Откатить к старой версии
    python scripts/migrate_to_refactored.py --cleanup   # Удалить старый код (ОСТОРОЖНО!)
"""

import os
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path


# Пути
PLUGIN_ROOT = Path(__file__).parent.parent
SRC_DIR = PLUGIN_ROOT / 'src'
BACKUP_DIR = PLUGIN_ROOT / 'backup_legacy'

# Файлы старой версии для бэкапа/удаления
LEGACY_FILES = [
    'src/dxf_postgis_converter.py',
    'src/gui/import_dialog.py',
    'src/gui/main_dialog.py',
    'src/db/database.py',
]

# Соответствие старых и новых файлов
FILE_MAPPINGS = {
    'src/dxf_postgis_converter.py': 'src/dxf_postgis_converter_refactored.py',
    'src/gui/import_dialog.py': 'src/gui/import_dialog_refactored.py',
    'src/gui/main_dialog.py': 'src/gui/main_dialog_refactored.py',
}


def backup_legacy_files():
    """Создать резервную копию старых файлов."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = BACKUP_DIR / timestamp
    
    print(f"Creating backup in: {backup_path}")
    backup_path.mkdir(parents=True, exist_ok=True)
    
    for file_path in LEGACY_FILES:
        src = PLUGIN_ROOT / file_path
        if src.exists():
            # Сохраняем структуру директорий
            rel_path = Path(file_path)
            dst = backup_path / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src, dst)
            print(f"  Backed up: {file_path}")
        else:
            print(f"  Skipped (not found): {file_path}")
    
    # Сохраняем информацию о бэкапе
    info_file = backup_path / 'backup_info.txt'
    with open(info_file, 'w', encoding='utf-8') as f:
        f.write(f"Backup created: {datetime.now().isoformat()}\n")
        f.write(f"Files:\n")
        for file_path in LEGACY_FILES:
            f.write(f"  - {file_path}\n")
    
    print(f"\n✓ Backup complete: {backup_path}")
    return backup_path


def migrate_to_refactored():
    """Переключить на рефакторированную версию."""
    print("Migrating to refactored version...")
    
    # Обновляем __init__.py для использования новой версии
    init_file = PLUGIN_ROOT / '__init__.py'
    
    # Читаем текущий __init__.py
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверяем, не мигрировано ли уже
    if 'USE_REFACTORED' in content or 'migration_bridge' in content:
        print("Already migrated or migration bridge in use.")
        return
    
    # Создаём бэкап __init__.py
    backup_init = PLUGIN_ROOT / '__init__.py.backup'
    shutil.copy2(init_file, backup_init)
    print(f"  Backed up __init__.py to {backup_init}")
    
    # Заменяем импорт
    new_content = content.replace(
        'from .src.dxf_postgis_converter import DxfPostGISConverter',
        '''# Migration to refactored version
from .src.migration_bridge import get_plugin_class
DxfPostGISConverter = get_plugin_class()'''
    )
    
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    # Устанавливаем переменную окружения
    print("\n  To enable refactored version, set environment variable:")
    print("    set USE_REFACTORED_PLUGIN=1")
    
    print("\n✓ Migration complete. Restart QGIS to apply changes.")


def rollback_migration():
    """Откатить к старой версии."""
    print("Rolling back to legacy version...")
    
    init_file = PLUGIN_ROOT / '__init__.py'
    backup_init = PLUGIN_ROOT / '__init__.py.backup'
    
    if backup_init.exists():
        shutil.copy2(backup_init, init_file)
        print(f"  Restored __init__.py from backup")
        print("\n✓ Rollback complete. Restart QGIS to apply changes.")
    else:
        print("  No backup found. Manual restoration required.")
        print("  Replace content of __init__.py with:")
        print("    from .src.dxf_postgis_converter import DxfPostGISConverter")


def cleanup_legacy_code():
    """Удалить старый код (ОСТОРОЖНО!)."""
    print("=" * 60)
    print("WARNING: This will DELETE legacy code files!")
    print("=" * 60)
    print("\nFiles to be deleted:")
    for file_path in LEGACY_FILES:
        src = PLUGIN_ROOT / file_path
        status = "EXISTS" if src.exists() else "NOT FOUND"
        print(f"  [{status}] {file_path}")
    
    print("\nThis action is IRREVERSIBLE without backup!")
    
    response = input("\nType 'DELETE' to confirm: ")
    if response != 'DELETE':
        print("Aborted.")
        return
    
    # Проверяем наличие бэкапа
    if not BACKUP_DIR.exists() or not any(BACKUP_DIR.iterdir()):
        print("\nNo backup found! Creating backup first...")
        backup_legacy_files()
    
    # Удаляем файлы
    deleted = 0
    for file_path in LEGACY_FILES:
        src = PLUGIN_ROOT / file_path
        if src.exists():
            src.unlink()
            print(f"  Deleted: {file_path}")
            deleted += 1
    
    print(f"\n✓ Cleanup complete. Deleted {deleted} files.")
    print(f"  Backup available at: {BACKUP_DIR}")


def show_status():
    """Показать текущий статус миграции."""
    print("Migration Status")
    print("=" * 60)
    
    # Проверяем __init__.py
    init_file = PLUGIN_ROOT / '__init__.py'
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'migration_bridge' in content:
        print("Mode: Migration Bridge (switchable)")
    elif 'dxf_postgis_converter_refactored' in content:
        print("Mode: Refactored Only")
    else:
        print("Mode: Legacy")
    
    # Статус файлов
    print("\nLegacy Files:")
    for file_path in LEGACY_FILES:
        src = PLUGIN_ROOT / file_path
        status = "✓ exists" if src.exists() else "✗ deleted"
        print(f"  [{status}] {file_path}")
    
    print("\nRefactored Files:")
    for old, new in FILE_MAPPINGS.items():
        src = PLUGIN_ROOT / new
        status = "✓ exists" if src.exists() else "✗ missing"
        print(f"  [{status}] {new}")
    
    # Бэкапы
    print("\nBackups:")
    if BACKUP_DIR.exists():
        backups = list(BACKUP_DIR.iterdir())
        if backups:
            for backup in sorted(backups, reverse=True)[:5]:
                print(f"  - {backup.name}")
        else:
            print("  No backups found")
    else:
        print("  No backup directory")
    
    # Переменная окружения
    print("\nEnvironment:")
    use_refactored = os.environ.get('USE_REFACTORED_PLUGIN', '0')
    print(f"  USE_REFACTORED_PLUGIN={use_refactored}")


def main():
    parser = argparse.ArgumentParser(
        description='Migration tool for DXF-PostGIS-Converter refactoring'
    )
    parser.add_argument('--backup', action='store_true', 
                        help='Create backup of legacy files')
    parser.add_argument('--migrate', action='store_true',
                        help='Switch to refactored version')
    parser.add_argument('--rollback', action='store_true',
                        help='Rollback to legacy version')
    parser.add_argument('--cleanup', action='store_true',
                        help='Delete legacy files (DANGEROUS!)')
    parser.add_argument('--status', action='store_true',
                        help='Show migration status')
    
    args = parser.parse_args()
    
    if args.backup:
        backup_legacy_files()
    elif args.migrate:
        migrate_to_refactored()
    elif args.rollback:
        rollback_migration()
    elif args.cleanup:
        cleanup_legacy_code()
    elif args.status:
        show_status()
    else:
        show_status()
        print("\nUse --help for available commands")


if __name__ == '__main__':
    main()
