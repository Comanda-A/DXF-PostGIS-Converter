from qgis.PyQt.QtWidgets import QTreeWidget, QTreeWidgetItem

class LayerSetViewer:
    def __init__(self, db_manager, tree_widget):
        self.db_manager = db_manager
        self.tree_widget = tree_widget

    def load_layer_sets(self):
        if not self.db_manager.connection:
            print("No database connection.")
            return

        try:
            cursor = self.db_manager.connection.cursor()
            query = """
            SELECT ls.id, ls.name, ls.description, l.layer_name, l.json_data
            FROM layer_sets ls
            LEFT JOIN layers l ON ls.id = l.layer_set_id
            ORDER BY ls.id, l.id;
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            self.tree_widget.clear()

            if not rows:
                no_data_item = QTreeWidgetItem(["No data available"])
                self.tree_widget.addTopLevelItem(no_data_item)
                return

            current_layer_set_id = None
            current_layer_set_item = None

            for row in rows:
                layer_set_id, name, description, layer_name, json_data = row

                if layer_set_id != current_layer_set_id:
                    current_layer_set_item = QTreeWidgetItem([str(layer_set_id), name, description])
                    self.tree_widget.addTopLevelItem(current_layer_set_item)
                    current_layer_set_id = layer_set_id

                layer_item = QTreeWidgetItem([layer_name, json_data])
                current_layer_set_item.addChild(layer_item)

            cursor.close()
        except:
            pass
