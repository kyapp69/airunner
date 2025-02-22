import importlib
import os
from aihandler.util import get_extensions_from_path


class ExtensionMixin:
    """
    This is a mixin class that is used to manage extensions.
    """
    active_extensions = []

    def initialize(self):
        for tab_name in self.tabs.keys():
            self.do_generator_tab_injection(self.tabs[tab_name], tab_name)
        self.do_menubar_injection()
        self.do_toolbar_injection()

    def get_extensions_from_path(self):
        """
        Initialize extensions by loading them from the extensions_directory.
        These are extensions that have been activated by the user.
        Extensions can be activated by manually adding them to the extensions folder
        or by browsing for them in the extensions menu and activating them there.

        This method initializes active extensions.
        :return:
        """
        extensions = []
        base_path = self.settings_manager.settings.model_base_path.get()
        extension_path = os.path.join(base_path, "extensions")
        if not os.path.exists(extension_path):
            return extensions
        available_extensions = get_extensions_from_path(extension_path)
        for extension in available_extensions:
            if extension.name.get() in self.settings_manager.settings.enabled_extensions.get():
                repo = extension.repo.get()
                name = repo.split("/")[-1]
                path = os.path.join(extension_path, name)
                if os.path.exists(path):
                    for f in os.listdir(path):
                        if os.path.isfile(os.path.join(path, f)) and f == "main.py":
                            # get Extension class from main.py
                            spec = importlib.util.spec_from_file_location("main", os.path.join(path, f))
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            extension_class = getattr(module, "Extension")
                            extensions.append(extension_class(self.settings_manager))
        self.settings_manager.settings.active_extensions.set(extensions)

    def do_generator_tab_injection(self, tab, tab_name):
        """
        Ibjects extensions into the generator tab widget.
        :param tab_name:
        :param tab:
        :return:
        """
        for extension in self.settings_manager.settings.active_extensions.get():
            extension.generator_tab_injection(tab, tab_name)

    def do_menubar_injection(self):
        for extension in self.settings_manager.settings.active_extensions.get():
            extension.menubar_injection(self.window.menubar)

    def do_toolbar_injection(self):
        for extension in self.settings_manager.settings.active_extensions.get():
            extension.toolbar_injection(self.window.horizontalFrame)
