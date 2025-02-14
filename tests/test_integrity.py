import os
import sys
import ezdxf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.database import PATTERN_DATABASE_URL, Base, export_dxf, import_dxf, get_all_files_from_db
from src.dxf.dxf_handler import DXFHandler
from src.tree_widget_handler import TreeWidgetHandler


def test_dxf_integrity(input_dxf_path: str, output_dxf_path: str = None):
    """
    Проверка целостности конвертации DXF -> PostGIS -> DXF
    
    Args:
        input_dxf_path (str): Путь к входному DXF файлу
        output_dxf_path (str): Путь для сохранения выходного DXF файла (опционально)
    """
    # Параметры подключения к тестовой БД
    test_params = {
        "username": "postgres",
        "password": "123",
        "address": "localhost",
        "port": "5432",
        "dbname": "test"
    }

    if output_dxf_path is None:
        output_dir = os.path.join(os.path.dirname(input_dxf_path), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_dxf_path = os.path.join(output_dir, "integrity_test_result.dxf")

    print(f"Начало проверки целостности конвертации файла: {input_dxf_path}")

    # Очистка БД перед тестом
    db_url = PATTERN_DATABASE_URL.format(**test_params)
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Удаляем данные из таблиц в правильном порядке
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        print("БД очищена успешно")
    except Exception as e:
        print(f"Ошибка при очистке БД: {str(e)}")
        return
    finally:
        session.close()

    try:
        # Загружаем DXF файл
        dxf_handler = DXFHandler(None, None, None)
        layers_entities, filename = dxf_handler.read_dxf_file(input_dxf_path)
        print(f"Файл {filename} успешно загружен")

        # Экспортируем в БД
        export_dxf(**test_params, dxf_handler=dxf_handler)
        print("Данные успешно экспортированы в БД")

        # Импортируем обратно в DXF
        files = get_all_files_from_db(**test_params)
        if files and len(files) > 0:
            file_id = files[0]['id']
            import_dxf(**test_params, file_id=file_id, path=output_dxf_path)
            print(f"Данные успешно импортированы в новый файл: {output_dxf_path}")
        else:
            print("Файлы не найдены в БД")
            return

        # Проверяем целостность
        orig_doc = ezdxf.readfile(input_dxf_path)
        new_doc = ezdxf.readfile(output_dxf_path)

        # Сравниваем количество объектов
        orig_count = len(list(orig_doc.modelspace()))
        new_count = len(list(new_doc.modelspace()))
        print(f"Количество объектов в оригинале: {orig_count}")
        print(f"Количество объектов в новом файле: {new_count}")

        # Проверяем слои
        orig_layers = set(layer.dxf.name for layer in orig_doc.layers)
        new_layers = set(layer.dxf.name for layer in new_doc.layers)
        
        if orig_layers == new_layers:
            print("Все слои сохранены корректно")
        else:
            missing_layers = orig_layers - new_layers
            if missing_layers:
                print(f"Отсутствующие слои: {missing_layers}")

        print("Проверка целостности завершена")

    except Exception as e:
        print(f"Ошибка при проверке целостности: {str(e)}")

if __name__ == "__main__":
    input_file = r"C:\Users\nikita\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\DXF-PostGIS-Converter\dxf_examples\example.dxf"
    test_dxf_integrity(input_file)
