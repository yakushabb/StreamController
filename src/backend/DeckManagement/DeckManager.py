"""
Author: Core447
Year: 2023

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This programm comes with ABSOLUTELY NO WARRANTY!

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
# Import Python modules
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices import StreamDeck
from StreamDeck.ImageHelpers import PILHelper
from loguru import logger as log
from usbmonitor import USBMonitor
import os

# Import own modules
from src.backend.DeckManagement.DeckController import DeckController
from src.backend.PageManagement.PageManager import PageManager
from src.backend.SettingsManager import SettingsManager
from src.backend.DeckManagement.HelperMethods import get_sys_param_value, recursive_hasattr
from src.backend.DeckManagement.Subclasses.FakeDeck import FakeDeck

import gi
from gi.repository import GLib

# Import globals
import globals as gl

class DeckManager:
    def __init__(self):
        #TODO: Maybe outsource some objects
        self.deck_controller: list[DeckController] = []
        self.fake_deck_controller = []
        self.settings_manager = SettingsManager()
        self.page_manager = gl.page_manager
        # self.page_manager.load_pages()

        # USB monitor to detect connections and disconnections
        self.usb_monitor = USBMonitor()
        self.usb_monitor.start_monitoring(on_connect=self.on_connect, on_disconnect=self.on_disconnect)

    def load_decks(self):
        decks=DeviceManager().enumerate()
        for deck in decks:
            try:
                if not deck.is_open():
                    deck.open()
            except:
                log.error("Failed to open deck. Maybe it's already connected to another instance?")
                continue
            if not deck.is_visual():
                continue
            deck_controller = DeckController(self, deck)
            self.deck_controller.append(deck_controller)

        # Load fake decks
        self.load_fake_decks()

    def load_fake_decks(self):
        old_n_fake_decks = len(self.fake_deck_controller)
        n_fake_decks = int(gl.settings_manager.load_settings_from_file(os.path.join(gl.DATA_PATH, "settings", "settings.json")).get("dev", {}).get("n-fake-decks", 0))

        if n_fake_decks > old_n_fake_decks:
            log.info(f"Loading {n_fake_decks - old_n_fake_decks} fake deck(s)")
            # Load difference in number of fake decks
            for controller in range(n_fake_decks - old_n_fake_decks):
                a = f"Fake Deck {len(self.fake_deck_controller)+1}"
                fake_deck = FakeDeck(serial_number = f"fake-deck-{len(self.fake_deck_controller)+1}", deck_type=f"Fake Deck {len(self.fake_deck_controller)+1}")
                self.add_newly_connected_deck(fake_deck, is_fake=True)

            # Update header deck switcher if the new deck is the only one
            if len(self.deck_controller) == 1 and False:
                # Check if ui is loaded - if not it will grab the controller automatically
                if recursive_hasattr(gl, "app.main_win.header_bar.deckSwitcher"):
                    gl.app.main_win.header_bar.deckSwitcher.set_show_switcher(True)

        elif n_fake_decks < old_n_fake_decks:
            # Remove difference in number of fake decks
            log.info(f"Removing {old_n_fake_decks - n_fake_decks} fake deck(s)")
            for controller in self.fake_deck_controller[-(old_n_fake_decks - n_fake_decks):]:
                # Remove controller from fake_decks
                self.fake_deck_controller.remove(controller)
                # Remove controller from main list
                self.deck_controller.remove(controller)
                # Remove deck page on stack
                gl.app.main_win.leftArea.deck_stack.remove_page(controller)

            # Update header deck switcher if there are no more decks
            if len(self.deck_controller) == 0 and False:
                # Check if ui is loaded - if not it will grab the controller automatically
                if recursive_hasattr(gl, "app.main_win.header_bar.deckSwitcher"):
                    gl.app.main_win.header_bar.deckSwitcher.set_show_switcher(False)
        if hasattr(gl.app, "main_win"):
            gl.app.main_win.check_for_errors()


    def on_connect(self, device_id, device_info):
        log.info(f"Device {device_id} with info: {device_info} connected")
        # Check if it is a supported device
        if device_info["ID_VENDOR"] != "Elgato":
            return
        
        
        self.connect_new_decks()

    def connect_new_decks(self):
        # Get already loaded deck serial ids
        loaded_deck_ids = []
        for controller in self.deck_controller:
            loaded_deck_ids.append(controller.deck.id())
        
        for deck in DeviceManager().enumerate():
            if deck.id() in loaded_deck_ids:
                continue

            # Add deck
            self.add_newly_connected_deck(deck)

        gl.app.main_win.check_for_errors()


    def on_disconnect(self, device_id, device_info):
        log.info(f"Device {device_id} with info: {device_info} disconnected")
        if device_info["ID_VENDOR"] != "Elgato":
            return

        for controller in self.deck_controller:
            if not controller.deck.connected():
                self.remove_controller(controller)

        gl.app.main_win.check_for_errors()

    def remove_controller(self, deck_controller: DeckController) -> None:
        self.deck_controller.remove(deck_controller)
        gl.app.main_win.leftArea.deck_stack.remove_page(deck_controller)
        deck_controller.delete()
        del deck_controller


    def add_newly_connected_deck(self, deck:StreamDeck, is_fake: bool = False):
        deck_controller = DeckController(self, deck)

        # Check if ui is loaded - if not it will grab the controller automatically
        if recursive_hasattr(gl, "app.main_win.leftArea.deck_stack"):
            # Add to deck stack
            GLib.idle_add(gl.app.main_win.leftArea.deck_stack.add_page, deck_controller)

        if recursive_hasattr(gl, "app.main_win.sidebar.page_selector"):
            GLib.idle_add(gl.app.main_win.sidebar.page_selector.update)



        self.deck_controller.append(deck_controller)
        if is_fake:
            self.fake_deck_controller.append(deck_controller)

        if not recursive_hasattr(gl, "app.main_win."):
            return
        gl.app.main_win.check_for_errors()

    def close_all(self):
        log.info("Closing all decks")
        for controller in self.deck_controller:
            if controller.deck is None:
                return
            if not controller.deck.is_open():
                return
            
            log.info(f"Closing deck: {controller.deck.get_serial_number()}")
            controller.clear()
            controller.deck.close()