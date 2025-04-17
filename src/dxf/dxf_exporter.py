from ezdxf import xref as xref
from ezdxf.xref import ConflictPolicy

from .dxf_handler import DXFHandler
from ..logger.logger import Logger


class DXFExporter:
    """
    Экспортирует выбранные сущности в новый DXF файл.
    """

    def __init__(self, handler: DXFHandler):
        self.handler = handler

    def export_selected_entities(self, filename: str, output_file: str):
        """
        Экспортирует выбранные сущности в новый DXF файл.

        :param filename: Имя исходного DXF файла.
        :param output_file: Имя выходного DXF файла.
        """
        if filename not in self.handler.selected_entities:
            Logger.log_error(f"Нет выбранных сущностей для файла {filename}.")
            return

        selected_entities = self.handler.selected_entities[filename]
        if not selected_entities:
            Logger.log_error(f"Нет выбранных сущностей для экспорта из файла {filename}.")
            return

        try:
            # Используем функцию write_block из модуля xref для создания нового документа
            # с выбранными сущностями. Эта функция также копирует все необходимые ресурсы,
            # такие как слои, типы линий, стили текста и т.д.
            new_doc = xref.write_block(selected_entities, origin=(0, 0, 0))

            layout_names = [name for name in self.handler.dxf[filename].layout_names() if name != "Model"]
            try:
                for layout_name in layout_names:
                    xref.load_paperspace(self.handler.dxf[filename].paperspace(layout_name), new_doc, conflict_policy=ConflictPolicy.NUM_PREFIX)
            except Exception as e:
                Logger.log_error(f"Ошибка при загрузке layout {layout_name}: {e}")
            new_doc.delete_layout('Layout1')

            # Сохраняем новый документ
            new_doc.saveas(output_file)
            Logger.log_message(f"Выбранные сущности успешно экспортированы в файл {output_file}.")
            return True

        except Exception as e:
            Logger.log_error(f"Ошибка при экспорте сущностей: {e}")
            return False
