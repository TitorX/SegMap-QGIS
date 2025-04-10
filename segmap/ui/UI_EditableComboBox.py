from PyQt5.QtWidgets import (
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QListView,
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QSizePolicy,
)


class UI_EditableComboBox(QWidget):
    """
    A custom widget that combines a QComboBox with an Edit button.
    The Edit button opens a dialog for adding and deleting items in the combo box.
    The dialog allows for extended selection like a file explorer.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.select = QComboBox(self)
        self.select.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Allow combo_box to take as much space as possible
        self.edit_button = QPushButton("Edit", self)
        self.edit_button.clicked.connect(self.show_edit_dialog)
        self.edit_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)  # Keep edit_button as small as possible while showing all text

        layout = QHBoxLayout()
        layout.addWidget(self.select)
        layout.addWidget(self.edit_button)
        self.setLayout(layout)

        self.edit_enabled = True

    def show_edit_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit")

        list_view = QListView(dialog)
        list_view.setEditTriggers(
            QListView.NoEditTriggers
        )  # Disable editing of existing items
        list_view.setSelectionMode(
            QListView.ExtendedSelection
        )  # Enable extended selection mode for file explorer-like behavior
        list_view.setModel(self.select.model())

        add_line_edit = QLineEdit(dialog)
        add_line_edit.setPlaceholderText("New Item")

        add_button = QPushButton("Add", dialog)
        add_button.setEnabled(False)  # Initially disable the button
        add_button.clicked.connect(lambda: self.add_item(add_line_edit, list_view))

        add_line_edit.textChanged.connect(
            lambda text: add_button.setEnabled(
                bool(text.strip())
            )  # Enable only if text is not empty
        )

        delete_button = QPushButton("Delete", dialog)
        delete_button.setEnabled(False)
        delete_button.clicked.connect(lambda: self.delete_item(list_view))

        list_view.selectionModel().selectionChanged.connect(
            lambda: delete_button.setEnabled(bool(list_view.selectedIndexes()))
        )

        button_box = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        button_box.rejected.connect(
            dialog.reject
        )  # Connect Close button to close the dialog

        vbox = QVBoxLayout()
        vbox.addWidget(list_view)
        vbox.addWidget(add_line_edit)
        vbox.addWidget(add_button)
        vbox.addWidget(delete_button)
        vbox.addWidget(button_box)
        dialog.setLayout(vbox)

        # Add shortcut for Enter key
        add_line_edit.returnPressed.connect(
            lambda: add_button.click()
        )  # Enter to add if focused on line edit

        dialog.exec_()

    def add_item(self, add_line_edit, list_view):
        item_text = add_line_edit.text()
        if item_text:
            # Check if the item already exists in the list
            model = list_view.model()
            for row in range(model.rowCount()):
                if model.data(model.index(row, 0)) == item_text:
                    # If item exists, select it in the list
                    list_view.setCurrentIndex(model.index(row, 0))
                    add_line_edit.clear()
                    return

            # If item does not exist, add it
            self.select.addItem(item_text)
            add_line_edit.clear()
            list_view.model().layoutChanged.emit()

    def delete_item(self, list_view):
        selected_indexes = list_view.selectedIndexes()
        if selected_indexes:
            for index in sorted(selected_indexes, key=lambda x: x.row(), reverse=True):
                self.select.removeItem(index.row())
            list_view.model().layoutChanged.emit()

    def set_edit_enabled(self, enabled):
        self.edit_enabled = enabled
        self.edit_button.setVisible(enabled)
