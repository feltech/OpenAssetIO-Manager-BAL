import os

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtWidgets import QTableWidgetSelectionRange

from openassetio.trait import TraitsData
from openassetio.ui.managerApi import UIDelegateInterface
from openassetio.ui import UIDelegateState, UIDelegateRequest, access
from openassetio_mediacreation.traits.identity import DisplayNameTrait
from openassetio_mediacreation.traits.content import LocatableContentTrait
from openassetio_mediacreation.traits.ui import (
    SingularTrait,
    TabbedTrait,
    InPlaceTrait,
    DetachedTrait,
    BrowserTrait,
    EntityProviderTrait,
    InlineTrait,
    EntityInfoTrait,
)

from ..BasicAssetLibraryInterface import (
    ENV_VAR_IDENTIFIER_OVERRIDE,
    DEFAULT_IDENTIFIER,
)

from .. import bal
from ..BasicAssetLibraryInterface import BasicAssetLibraryInterface


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
        uiState = UIDelegateState()
        if BrowserTrait.isImbuedTo(uiTraits) and EntityProviderTrait.isImbuedTo(uiTraits):
            if uiAccess == access.UIAccess.kRead:
                widget = self.__create_read_asset_browser(
                    context.managerState.manager,
                    context.managerState.library,
                    uiTraits,
                    uiDelegateRequest,
                )
            else:
                widget = self.__create_write_asset_browser(
                    context.managerState.manager,
                    context.managerState.library,
                    uiTraits,
                    uiDelegateRequest,
                )
        elif InlineTrait.isImbuedTo(uiTraits) and EntityProviderTrait.isImbuedTo(uiTraits):
            widget = self.__create_inline_entity_box(
                context.managerState.manager,
                context.managerState.library,
                uiTraits,
                uiDelegateRequest,
                uiState,
                uiAccess,
            )
        elif InlineTrait.isImbuedTo(uiTraits) and EntityInfoTrait.isImbuedTo(uiTraits):
            widget = self.__create_inline_entity_info(
                context.managerState.library, uiDelegateRequest, uiAccess, uiState
            )
        else:
            return None

        # Add a tab to the container.
        if InPlaceTrait.isImbuedTo(uiTraits):
            container = uiDelegateRequest.nativeData
            if container is not None:
                if TabbedTrait.isImbuedTo(uiTraits):
                    tab_idx = container.addTab(widget, "BAL's Asset Browser")
                    container.setCurrentIndex(tab_idx)
                else:
                    container.layout().addWidget(widget)

        if DetachedTrait.isImbuedTo(uiTraits):
            uiState.nativeData = widget

        return uiState

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

    def __create_inline_entity_box(self, manager, library, uiTraits, uiRequest, uiState, uiAccess):
        # Create a horizontal layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        # Create a faded label with the text "bal:///"
        prefix_label = QtWidgets.QLabel("bal:///")
        # Create a new color with reduced opacity
        faded_color = prefix_label.palette().color(QtGui.QPalette.ColorRole.WindowText)
        faded_color.setAlpha(128)
        palette = prefix_label.palette()
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, faded_color)
        prefix_label.setPalette(palette)
        layout.addWidget(prefix_label)

        # Create an autocomplete single-line text box for entity selection
        entity_input = QtWidgets.QLineEdit()
        entity_completer = QtWidgets.QCompleter()
        entity_input.setCompleter(entity_completer)

        # Set up the completer model
        entity_model = QtCore.QStringListModel()
        entity_model.setStringList(library["entities"].keys())
        entity_completer.setModel(entity_model)

        layout.addWidget(entity_input)

        # Create a dropdown for version selection
        version_dropdown = QtWidgets.QComboBox()
        layout.addWidget(version_dropdown)

        def update_versions():
            entity_id = entity_input.text()
            version_dropdown.clear()

            if library["entities"].get(entity_id) is None:
                return

            # Get versions for the selected entity
            versions = list(
                reversed(
                    [f"v{n + 1}" for n in range(len(library["entities"][entity_id]["versions"]))]
                )
            )
            if not versions:
                # Empty versions lists is legit. E.g. overrideByAccess
                # used instead.
                return
            version_dropdown.addItems(versions)
            version_num = version_dropdown.count()
            selected_value = f"bal:///{entity_id}?v={version_num}"

            uiState.entityReferences = [manager._createEntityReference(selected_value)]
            uiRequest.stateChangedCallback(uiState)

        def select_version():
            entity_id = entity_input.text()
            if library["entities"].get(entity_id) is None:
                return
            if not version_dropdown.count():
                return
            version_num = version_dropdown.count() - version_dropdown.currentIndex()
            selected_value = f"bal:///{entity_id}?v={version_num}"
            uiState.entityReferences = [manager._createEntityReference(selected_value)]
            uiRequest.stateChangedCallback(uiState)

        # Connect signals
        entity_input.textChanged.connect(update_versions)
        version_dropdown.currentIndexChanged.connect(select_version)

        # Create a widget to hold the layout
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)

        def on_update_request(uiRequest):
            if uiRequest.entityReferences:
                entity_ref_str = uiRequest.entityReferences[0].toString()

                entity_info = BasicAssetLibraryInterface.parse_entity_ref(entity_ref_str, uiAccess)
                entity_input.setText(entity_info.name)
                update_versions()
                if entity_info.version is not None:
                    version_dropdown.setCurrentText(f"v{entity_info.version}")

        uiState.updateRequestCallback = on_update_request
        on_update_request(uiRequest)

        return widget

    def __create_inline_entity_info(self, library, uiRequest, uiAccess, uiState):
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        display_name = QtWidgets.QLabel()

        h_layout = QtWidgets.QHBoxLayout()
        h_layout.addStretch(1)
        h_layout.addWidget(display_name)
        h_layout.addStretch(1)
        layout.addLayout(h_layout)

        comment_box = QtWidgets.QTextEdit()
        layout.addWidget(comment_box)
        # Make it non-editable
        comment_box.setReadOnly(True)

        # Set a fixed height for 5 lines of text
        font_metrics = QtGui.QFontMetrics(comment_box.font())
        line_spacing = font_metrics.lineSpacing()
        comment_box.setFixedHeight(5 * line_spacing)
        # Enable vertical scrollbar
        comment_box.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        def update_request_cb(updated_request):
            if updated_request.entityReferences:
                entity_ref_str = updated_request.entityReferences[0].toString()
                entity_info = BasicAssetLibraryInterface.parse_entity_ref(entity_ref_str, uiAccess)
                entity = bal.entity(entity_info, library)
                # Set the text
                display_name.setText(
                    entity.traits.get(DisplayNameTrait.kId, {}).get("name", "unknown")
                )
                comment_box.setText(entity.traits.get("bal:custom", {}).get("comment", "N/A"))

        update_request_cb(uiRequest)

        uiState.updateRequestCallback = update_request_cb

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget


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
