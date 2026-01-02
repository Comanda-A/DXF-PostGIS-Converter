# -*- coding: utf-8 -*-
"""
Presentation Layer - UI компоненты.

Содержит:
- dialogs/ - Диалоговые окна
- widgets/ - UI виджеты
- resources/ - UI ресурсы (.ui файлы)
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    'ConverterDialog',
    'ImportDialog',
    'ExportDialog',
    'SchemaSelectorDialog',
    'CredentialsDialog',
    'ProvidersDialog',
    'AttributeDialog',
    'ColumnMappingDialog',
    'InfoDialog',
    'TreeWidgetHandler',
    'PreviewDialog',
]


def __getattr__(name: str):
    """Lazy loading of dialogs to avoid circular imports."""
    if name == 'ConverterDialog':
        from .dialogs.main_dialog import ConverterDialog
        return ConverterDialog
    elif name == 'ImportDialog':
        from .dialogs.import_dialog import ImportDialog
        return ImportDialog
    elif name == 'ExportDialog':
        from .dialogs.export_dialog import ExportDialog
        return ExportDialog
    elif name == 'SchemaSelectorDialog':
        from .dialogs.schema_selector_dialog import SchemaSelectorDialog
        return SchemaSelectorDialog
    elif name == 'CredentialsDialog':
        from .dialogs.credentials_dialog import CredentialsDialog
        return CredentialsDialog
    elif name == 'ProvidersDialog':
        from .dialogs.providers_dialog import ProvidersDialog
        return ProvidersDialog
    elif name == 'AttributeDialog':
        from .dialogs.attribute_dialog import AttributeDialog
        return AttributeDialog
    elif name == 'ColumnMappingDialog':
        from .dialogs.column_mapping_dialog import ColumnMappingDialog
        return ColumnMappingDialog
    elif name == 'InfoDialog':
        from .dialogs.info_dialog import InfoDialog
        return InfoDialog
    elif name == 'TreeWidgetHandler':
        from .widgets.tree_widget_handler import TreeWidgetHandler
        return TreeWidgetHandler
    elif name == 'PreviewDialog':
        from .widgets.preview_components import PreviewDialog
        return PreviewDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
