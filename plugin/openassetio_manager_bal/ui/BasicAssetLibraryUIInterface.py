import os

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtWidgets import QTableWidgetSelectionRange

from openassetio.trait import TraitsData
from openassetio.ui.managerApi import UIDelegateInterface
from openassetio.ui import UIDelegateState, UIDelegateRequest, access
from openassetio_mediacreation.traits.identity import DisplayNameTrait
from openassetio_mediacreation.traits.content import LocatableContentTrait
from openassetio_mediacreation.traits.ui import SingularTrait

from ..BasicAssetLibraryInterface import (
    ENV_VAR_IDENTIFIER_OVERRIDE,
    DEFAULT_IDENTIFIER,
)


class BasicAssetLibraryUIInterface(UIDelegateInterface):

    def __init__(self):
        super(BasicAssetLibraryUIInterface, self).__init__()

    def displayName(self):
        return super().displayName()

    def identifier(self):
        return os.environ.get(ENV_VAR_IDENTIFIER_OVERRIDE, DEFAULT_IDENTIFIER)

    def populateUI(self, uiTraits, uiAccess, uiDelegateRequest, context, hostSession):
        # import pydevd_pycharm
        # pydevd_pycharm.settrace(
        #     "localhost", port=12345, stdoutToServer=True, stderrToServer=True, suspend=False
        # )
        # Get Qt widget container
        container: QtWidgets.QTabWidget = uiDelegateRequest.nativeData
        if uiAccess == access.UIAccess.kRead:
            browser = self.__create_read_asset_browser(
                context.managerState.manager,
                context.managerState.library,
                uiTraits,
                uiDelegateRequest,
            )
        else:
            browser = self.__create_write_asset_browser(
                context.managerState.manager,
                context.managerState.library,
                uiTraits,
                uiDelegateRequest,
            )

        # Add a tab to the container.
        tab_idx = container.addTab(browser, "BAL's Asset Browser")
        container.setCurrentIndex(tab_idx)

        return UIDelegateState(nativeData=browser)

    def __create_write_asset_browser(self, manager, library, ui_traits: TraitsData, request):
        # Create browser.
        browser = QtWidgets.QWidget()
        browser.setLayout(QtWidgets.QVBoxLayout())

        # Create the table
        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)

        name_column = 0
        qualified_name_column = 1
        version_column = 2

        # Populate the table
        row = 0
        matching_entity_ids = []

        for entity_id, entity_data in library["entities"].items():
            entity_versions = entity_data["versions"]
            if not entity_versions:
                continue
            latest_version = entity_versions[-1]
            if not entity_has_requested_traits(latest_version, request.entityTraitsDatas):
                continue

            matching_entity_ids.append(entity_id)
            table.insertRow(row)

            display_name = latest_version["traits"][DisplayNameTrait.kId]
            name = display_name["name"]
            qualified_name = display_name["qualifiedName"]
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setData(QtCore.Qt.UserRole, entity_id)
            table.setItem(row, name_column, name_item)

            table.setItem(row, qualified_name_column, QtWidgets.QTableWidgetItem(qualified_name))
            table.setItem(
                row, version_column, QtWidgets.QTableWidgetItem(f"v{len(entity_versions)}")
            )

            for entityReference in request.entityReferences:
                if entityReference.toString().startswith(f"bal:///{entity_id}"):
                    table.selectRow(row)
            row += 1

        # Set table properties
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.resizeColumnsToContents()

        # Add the table to the browser
        browser.layout().addWidget(table)

        # Allow constructing a new entity reference.

        new_entity = QtWidgets.QWidget()
        new_entity.setLayout(QtWidgets.QHBoxLayout())

        if not matching_entity_ids:
            matching_entity_ids.append("unknown/unknown")

        entity_name_parts = (entity_id.split("/") for entity_id in matching_entity_ids)
        entity_name_parts = (parts[:2] for parts in entity_name_parts)
        project_names, namespace_names = zip(*entity_name_parts)
        project_names = set(project_names)
        namespace_names = set(namespace_names)

        project_combo = QtWidgets.QComboBox()
        for project_name in project_names:
            project_combo.addItem(project_name)

        namespace_combo = QtWidgets.QComboBox()
        for namespace_name in namespace_names:
            namespace_combo.addItem(namespace_name)

        name_input = QtWidgets.QLineEdit()
        name_input.setPlaceholderText("Custom name...")

        new_entity.layout().addWidget(project_combo)
        new_entity.layout().addWidget(namespace_combo)
        new_entity.layout().addWidget(name_input)
        browser.layout().addWidget(new_entity)

        # Add an OK and Cancel button to the bottom of the browser.

        buttons = QtWidgets.QWidget()
        buttons.setLayout(QtWidgets.QHBoxLayout())

        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")

        buttons.layout().addWidget(ok_button)
        buttons.layout().addWidget(cancel_button)
        browser.layout().addWidget(buttons)

        # Call uiDelegateRequests.stateChangedCallback when OK button
        # clicked.

        def row_selection_changed_handler():
            selected_rows = table.selectionModel().selectedRows()
            selected_row_idx = selected_rows[0].row()
            selected_entity = table.item(selected_row_idx, name_column).data(
                QtCore.Qt.ItemDataRole.UserRole
            )
            entity_name_parts = selected_entity.split("/")
            project_combo.setCurrentText(entity_name_parts[0])
            namespace_combo.setCurrentText(entity_name_parts[1])
            name_input.setText("/".join(entity_name_parts[2:]))

        table.itemSelectionChanged.connect(row_selection_changed_handler)

        def ok_button_handler():
            project_name = project_combo.currentText()
            namespace_name = namespace_combo.currentText()
            entity_name = name_input.text()
            entity_id = f"bal:///{project_name}/{namespace_name}/{entity_name}"
            entity_reference = manager._createEntityReference(entity_id)
            request.stateChangedCallback(UIDelegateState(entityReferences=[entity_reference]))

        ok_button.clicked.connect(ok_button_handler)

        cancel_button.clicked.connect(lambda: request.stateChangedCallback(UIDelegateState()))

        return browser

    def __create_read_asset_browser(self, manager, library, ui_traits: TraitsData, request):
        # Create browser.
        browser = QtWidgets.QWidget()
        browser.setLayout(QtWidgets.QVBoxLayout())

        # Create the table
        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)

        name_column = 0
        qualified_name_column = 1
        version_column = 2

        def version_change_row_updater(entity_id, row, versions):
            def update_row(combo_idx):
                # Combo option 0 means "latest", 1 means 0, 2 means 1, etc.
                version_idx = combo_idx - 1 if combo_idx else len(versions) - 1
                version = versions[version_idx]
                display_name = version["traits"][DisplayNameTrait.kId]
                name = display_name["name"]
                qualified_name = display_name["qualifiedName"]
                name_item = QtWidgets.QTableWidgetItem(name)
                name_item.setData(QtCore.Qt.UserRole, entity_id)
                table.setItem(row, name_column, name_item)
                table.setItem(
                    row, qualified_name_column, QtWidgets.QTableWidgetItem(qualified_name)
                )

            return update_row

        # Populate the table
        row = 0

        for entity_id, entity_data in library["entities"].items():
            entity_versions = entity_data["versions"]
            if not entity_versions:
                continue
            latest_version = entity_versions[-1]
            if not entity_has_requested_traits(latest_version, request.entityTraitsDatas):
                continue

            table.insertRow(row)
            version_change_row_updater(entity_id, row, entity_versions)(0)

            # Create a dropdown for version selection
            version_combo = QtWidgets.QComboBox()
            version_combo.addItem("latest")
            for version_idx, _ in enumerate(entity_versions):
                version_combo.addItem(f"v{version_idx+1}")

            # Connect the combobox signal to the update method
            version_combo.currentIndexChanged.connect(
                version_change_row_updater(entity_id, row, entity_versions)
            )

            for entityReference in request.entityReferences:
                if entityReference.toString().startswith(f"bal:///{entity_id}"):
                    table.selectRow(row)

            table.setCellWidget(row, version_column, version_combo)
            row += 1

        # Set table properties
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)

        if SingularTrait.isImbuedTo(ui_traits):
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        else:
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.resizeColumnsToContents()

        # Add the table to the browser
        browser.layout().addWidget(table)

        # Add an OK and Cancel button to the bottom of the browser.
        buttons = QtWidgets.QWidget()
        buttons.setLayout(QtWidgets.QHBoxLayout())

        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")

        buttons.layout().addWidget(ok_button)
        buttons.layout().addWidget(cancel_button)
        browser.layout().addWidget(buttons)

        # Call uiDelegateRequests.stateChangedCallback when OK button
        # clicked.

        def ok_button_handler():
            selected_rows = table.selectionModel().selectedRows()
            entity_references = []
            for selected_row_item in selected_rows:
                selected_row_idx = selected_row_item.row()
                selected_entity = table.item(selected_row_idx, name_column).data(
                    QtCore.Qt.ItemDataRole.UserRole
                )
                ref_str = f"bal:///{selected_entity}"
                version_combo = table.cellWidget(selected_row_idx, version_column)
                selected_version = version_combo.currentIndex()
                if selected_version != 0:
                    ref_str += f"?v={selected_version}"
                entity_references.append(manager._createEntityReference(ref_str))

            request.stateChangedCallback(UIDelegateState(entityReferences=entity_references))

        ok_button.clicked.connect(ok_button_handler)

        cancel_button.clicked.connect(lambda: request.stateChangedCallback(UIDelegateState()))

        return browser


def entity_has_requested_traits(entity_version, requested_entity_traits_datas):
    # import pydevd_pycharm
    # pydevd_pycharm.settrace(
    #     'localhost', port=12345, stdoutToServer=True, stderrToServer=True)
    if not requested_entity_traits_datas:
        # If no traits then don't filter.
        return True
    for requested_entity_traits_data in requested_entity_traits_datas:
        requested_trait_set = requested_entity_traits_data.traitSet()
        entity_trait_set = set(entity_version["traits"].keys())
        if requested_trait_set <= entity_trait_set:
            locatableContentTrait = LocatableContentTrait(requested_entity_traits_data)
            if locatableContentTrait.isImbued():
                if entity_matches_mime_type(entity_version, locatableContentTrait.getMimeType()):
                    return True
            else:
                return True
    return False


def entity_matches_mime_type(entity_version, requested_mime_types_str):
    if requested_mime_types_str is None:
        return True
    entity_mime_types_str = entity_version["traits"][LocatableContentTrait.kId].get("mimeType")
    if entity_mime_types_str is None:
        return False

    requested_mime_types = set(requested_mime_types_str.split(","))
    entity_mime_types = set(entity_mime_types_str.split(","))
    if not entity_mime_types.isdisjoint(requested_mime_types):
        return True

    # Check for wildcards.
    requested_wildcard_mime_types = (mime for mime in requested_mime_types if mime.endswith("/*"))
    for wildcard_mime_type in requested_wildcard_mime_types:
        for mime_type in entity_mime_types:
            if mime_type.startswith(wildcard_mime_type[:-1]):
                return True
    return False
