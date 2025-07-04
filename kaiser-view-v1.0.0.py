import sys
import os
import json
import logging
import re
from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia, QtMultimediaWidgets
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QPixmap
from PIL import Image
from enum import Enum

# Logging setup
logging.basicConfig(filename='error.log', level=logging.ERROR)

# Constants
BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "MyImageFolder")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "config.json")
DEFAULT_CONFIG = {"favorites": [], "stretch_mode": False, "playback_speed": 100, "loop_video": True}

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

class StretchMode(Enum):
    DISABLED = 0
    ENABLED = 1

# Helper functions
def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as file:
                user_config = json.load(file)
            config.update(user_config)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to load configuration: {e}")
    return config

def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as file:
            json.dump(config, file, indent=4)
    except Exception as e:
        logging.error(f"Failed to save configuration: {e}")




# TransparentWindow class restored
class TransparentWindow(QtWidgets.QWidget):
    def __init__(self, media_path, playback_speed, loop_video):
        super().__init__()

        self.is_video = False
        self.is_web_video = False
        self.initial_resize_done = False

        self.playback_speed = playback_speed
        self.pixmap = None
        self.movie = None
        self.media_player = None
        self.video_widget = None
        self.browser = None
        self.volume = 50  # Default volume
        self.loop_video = loop_video

        # Determine file type
        ext = os.path.splitext(media_path)[1].lower()
        video_exts = ['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm']

        youtube_pattern = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
        is_youtube_url = youtube_pattern.match(media_path)

        try:
            if is_youtube_url:
                self.is_web_video = True
                self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
                self.resize(800, 450)
                self.browser = QWebEngineView()
                # Construct an embed URL for looping and autoplay
                video_id = is_youtube_url.group(6)
                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1"
                if self.loop_video:
                    embed_url += "&loop=1&playlist=" + video_id
                self.browser.setUrl(QtCore.QUrl(embed_url))
                layout = QtWidgets.QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self.browser)
                self.setup_dragging()

            elif ext in video_exts or media_path.startswith('http'):
                self.is_video = True
                self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
                self.resize(640, 480)  # Restore default size
                self.video_widget = QtMultimediaWidgets.QVideoWidget()
                video_layout = QtWidgets.QVBoxLayout()
                video_layout.setContentsMargins(0, 0, 0, 0)
                video_layout.addWidget(self.video_widget)
                self.setLayout(video_layout)
                self.media_player = QtMultimedia.QMediaPlayer(self)
                self.media_player.error.connect(self.media_player_error)
                self.media_player.setVideoOutput(self.video_widget)
                self.media_player.metaDataChanged.connect(self.on_meta_data_changed)
                if media_path.startswith('http'):
                    self.media_player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl(media_path)))
                else:
                    self.media_player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl.fromLocalFile(media_path)))
                self.media_player.setVolume(self.volume)
                self.set_loop(self.loop_video)
                self.media_player.play()
                self.setup_dragging()
            else:
                self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
                self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
                self.setWindowOpacity(1)
                self.image = Image.open(media_path)
                if self.image.format == 'GIF':
                    self.movie = QtGui.QMovie(media_path)
                    self.movie.setSpeed(self.playback_speed)
                    self.movie.start()
                    self.resize(self.movie.frameRect().size())
                else:
                    self.pixmap = QPixmap(media_path)
                    self.resize(self.pixmap.width(), self.pixmap.height())
                self.label = QtWidgets.QLabel(self)
                self.label.setAlignment(QtCore.Qt.AlignCenter)
                self.setup_dragging()
                self.update_image()
                self.timer = QtCore.QTimer(self)
                self.timer.timeout.connect(self.update_image)
                self.timer.start(50)
        except Exception as e:
            logging.error(f"Failed to open media: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open media: {e}")
            self.close()
            return

    def on_meta_data_changed(self):
        if not self.initial_resize_done:
            video_resolution = self.media_player.metaData("Resolution")
            if video_resolution:
                self.resize(video_resolution.width(), video_resolution.height())
                self.initial_resize_done = True

    def set_loop(self, loop):
        if self.is_video:
            if loop:
                self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)
            else:
                try:
                    self.media_player.mediaStatusChanged.disconnect(self.handle_media_status_changed)
                except TypeError:
                    pass # Ignore if not connected

    def handle_media_status_changed(self, status):
        if status == QtMultimedia.QMediaPlayer.EndOfMedia:
            self.media_player.play()

    def media_player_error(self):
        error_string = self.media_player.errorString()
        logging.error(f"Media player error: {error_string}")
        if error_string:
            QtWidgets.QMessageBox.critical(self, "Video Player Error", error_string)

    def setup_dragging(self):
        self._dragging = False
        self._drag_position = None

    def update_image(self):
        if self.is_video or self.is_web_video:
            return

        if self.movie:
            self.label.setMovie(self.movie)
        elif self.pixmap:
            scaled_pixmap = self.pixmap.scaled(
                self.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.label.setPixmap(scaled_pixmap)
        
        self.label.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        self.update_image()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPos() - self._drag_position)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging = False

    def closeEvent(self, event):
        if self.movie:
            self.movie.stop()
        if self.media_player:
            self.media_player.stop()
        if self.browser:
            self.browser.setUrl(QtCore.QUrl("about:blank"))

    def adjust_size(self, scale_factor):
        current_width = self.width()
        current_height = self.height()
        self.resize(int(current_width * scale_factor), int(current_height * scale_factor))

    def change_speed(self, delta):
        if self.movie:
            self.playback_speed = max(1, self.playback_speed + delta)  # Prevent speed <= 0
            self.movie.setSpeed(self.playback_speed)

    def change_volume(self, delta):
        if self.media_player:
            self.volume = max(0, min(100, self.volume + delta))
            self.media_player.setVolume(self.volume)

    def toggle_always_on_top(self):
        current_flags = self.windowFlags()
        if current_flags & QtCore.Qt.WindowStaysOnTopHint:
            self.setWindowFlags(current_flags & ~QtCore.Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(current_flags | QtCore.Qt.WindowStaysOnTopHint)
        self.show()  # Reapply flags


class App(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt5 Transparent Media Viewer")
        self.setGeometry(100, 100, 500, 200)

        self.config = load_config()
        self.image_window = None

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        load_button = QtWidgets.QPushButton('Load From File')
        load_button.clicked.connect(self.load_media)
        layout.addWidget(load_button)

        url_button = QtWidgets.QPushButton('Load From URL')
        url_button.clicked.connect(self.load_from_url)
        layout.addWidget(url_button)

        enlarge_button = QtWidgets.QPushButton('Enlarge Window')
        enlarge_button.clicked.connect(lambda: self.adjust_window_size(1.1))
        layout.addWidget(enlarge_button)

        shrink_button = QtWidgets.QPushButton('Shrink Window')
        shrink_button.clicked.connect(lambda: self.adjust_window_size(0.9))
        layout.addWidget(shrink_button)

        speed_up_button = QtWidgets.QPushButton('Speed Up (GIF)')
        speed_up_button.clicked.connect(lambda: self.adjust_speed(10))  # Increase speed by 10%
        layout.addWidget(speed_up_button)

        speed_down_button = QtWidgets.QPushButton('Slow Down (GIF)')
        speed_down_button.clicked.connect(lambda: self.adjust_speed(-10))  # Decrease speed by 10%
        layout.addWidget(speed_down_button)

        volume_up_button = QtWidgets.QPushButton('Volume Up (Video)')
        volume_up_button.clicked.connect(lambda: self.adjust_volume(10))
        layout.addWidget(volume_up_button)

        volume_down_button = QtWidgets.QPushButton('Volume Down (Video)')
        volume_down_button.clicked.connect(lambda: self.adjust_volume(-10))
        layout.addWidget(volume_down_button)

        favorites_button = QtWidgets.QPushButton('Show Favorites')
        favorites_button.clicked.connect(self.show_favorites)
        layout.addWidget(favorites_button)

        clear_button = QtWidgets.QPushButton('Clear Favorites')
        clear_button.clicked.connect(self.clear_favorites)
        layout.addWidget(clear_button)

        self.loop_video_checkbox = QtWidgets.QCheckBox('Loop Video')
        self.loop_video_checkbox.setChecked(self.config.get("loop_video", True))
        self.loop_video_checkbox.stateChanged.connect(self.toggle_loop_video)
        layout.addWidget(self.loop_video_checkbox)

    def toggle_loop_video(self, state):
        self.config["loop_video"] = state == QtCore.Qt.Checked
        save_config(self.config)
        if self.image_window and self.image_window.is_video:
            self.image_window.set_loop(self.config["loop_video"])

    def keyPressEvent(self, event):
        if self.image_window and event.key() == QtCore.Qt.Key_T:
            self.image_window.toggle_always_on_top()


    def adjust_window_size(self, scale_factor):
        if self.image_window:
            self.image_window.adjust_size(scale_factor)

    def adjust_speed(self, delta):
        if self.image_window:
            self.image_window.change_speed(delta)

    def adjust_volume(self, delta):
        if self.image_window:
            self.image_window.change_volume(delta)

    def load_media(self):
        media_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Media", "", "Media Files (*.png *.jpg *.jpeg *.gif *.mp4 *.avi *.mov *.wmv *.mkv *.webm)")
        if media_path:
            self.play_media(media_path)

    def load_from_url(self):
        url, ok = QtWidgets.QInputDialog.getText(self, 'Load From URL', 'Enter a video URL:')
        if ok and url:
            self.play_media(url)

    def play_media(self, media_path):
        if self.image_window:
            self.image_window.close()

        self.image_window = TransparentWindow(media_path, self.config["playback_speed"], self.config["loop_video"])
        self.image_window.show()

        # Ask if the user wants to add the media to favorites
        add_to_favorites = QtWidgets.QMessageBox.question(
            self, "Add to Favorites", "Do you want to add this file to your favorites?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if add_to_favorites == QtWidgets.QMessageBox.Yes:
            if media_path not in self.config["favorites"]:
                self.config["favorites"].append(media_path)
                save_config(self.config)
                QtWidgets.QMessageBox.information(self, "Added to Favorites", "The file has been added to your favorites.")
            else:
                QtWidgets.QMessageBox.information(self, "Already in Favorites", "This file is already in your favorites.")

    def show_favorites(self):
        items = [os.path.basename(f) for f in self.config["favorites"]]
        if not items:
            QtWidgets.QMessageBox.information(self, "No Favorites", "You have no favorite files.")
            return

        item, ok = QtWidgets.QInputDialog.getItem(self, "Favorites", "Choose a favorite to load:", items, 0, False)
        if ok and item:
            selected_media = self.config["favorites"][items.index(item)]
            if self.image_window:
                self.image_window.close()

            self.image_window = TransparentWindow(selected_media, self.config["playback_speed"], self.config["loop_video"])
            self.image_window.show()

    def clear_favorites(self):
        self.config["favorites"] = []
        save_config(self.config)
        QtWidgets.QMessageBox.information(self, "Favorites Cleared", "All favorites have been removed.")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())
