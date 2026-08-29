import sys
import threading
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QTextEdit, QLabel, QScrollArea, QLineEdit, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QThread, Signal, Property, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QBrush, QPen
import markdown2
import pygments
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from services.ai_service import generate_text_stream
import psutil

# --- QSS STYLING ---
GLOBAL_STYLES = """
QMainWindow { background-color: #090B12; }
QWidget#centralWidget { background-color: #090B12; }

/* Sidebar */
QFrame#sidebar {
    background-color: #111827;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}
QPushButton.navBtn {
    background-color: transparent;
    color: #9ca3af;
    text-align: left;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
}
QPushButton.navBtn:hover {
    background-color: rgba(47, 128, 255, 0.1);
    color: #2F80FF;
}

/* Chat Area */
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.2);
}

/* Input Bar */
QFrame#inputContainer {
    background-color: #171F2F;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 8px;
}
QLineEdit#chatInput {
    background-color: transparent;
    color: white;
    border: none;
    font-size: 15px;
}
QPushButton.iconBtn {
    background-color: transparent;
    color: #9ca3af;
    border-radius: 16px;
    padding: 8px;
    font-size: 16px;
}
QPushButton.iconBtn:hover {
    color: white;
}
QPushButton#sendBtn {
    color: #2F80FF;
}

/* Status Panel */
QFrame#statusPanel {
    background-color: #111827;
    border-left: 1px solid rgba(255, 255, 255, 0.05);
}
QLabel.statusHeader {
    color: #9ca3af;
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QFrame.statusCard {
    background-color: #171F2F;
    border-radius: 12px;
    padding: 12px;
}
QLabel.statusText {
    color: white;
    font-size: 13px;
}
"""

class AIStreamWorker(QThread):
    token_received = Signal(str)
    stream_finished = Signal()
    error_occurred = Signal(str)
    
    def __init__(self, command):
        super().__init__()
        self.command = command
        
    def run(self):
        try:
            generator = generate_text_stream(self.command)
            for chunk in generator:
                self.token_received.emit(chunk)
            self.stream_finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))

class ChatBubble(QFrame):
    def __init__(self, text, is_user=False):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setFrameStyle(QFrame.NoFrame)
        self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_display.document().setDocumentMargin(0)
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {'#2F80FF' if is_user else '#171F2F'};
                border-radius: 16px;
            }}
            QTextEdit {{
                background-color: transparent;
                color: white;
                font-family: 'Inter', sans-serif;
                font-size: 15px;
            }}
        """)
        
        self.layout.addWidget(self.text_display)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        self.raw_text = ""
        if text:
            self.append_text(text)
            
    def append_text(self, text):
        self.raw_text += text
        # Simple markdown rendering for now (QTextEdit supports basic HTML)
        html = markdown2.markdown(self.raw_text)
        self.text_display.setHtml(html)
        
        # Adjust height dynamically
        self.text_display.document().adjustSize()
        doc_height = self.text_display.document().size().height()
        self.text_display.setFixedHeight(int(doc_height) + 10)
        self.setFixedHeight(int(doc_height) + 40)

class HiraMainWindow(QMainWindow):
    def __init__(self, process_command_func):
        super().__init__()
        self.process_command_func = process_command_func
        self.setWindowTitle("HIRA V3 Native")
        self.resize(1200, 800)
        self.setStyleSheet(GLOBAL_STYLES)
        
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.init_sidebar()
        self.init_chat_area()
        self.init_status_panel()
        
        self.current_bubble = None
        
    def init_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(10)
        
        title = QLabel("HIRA.")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        sidebar_layout.addWidget(title)
        
        nav_items = ["Home", "Chat", "Voice Mode", "Files", "Automation", "Settings"]
        for item in nav_items:
            btn = QPushButton(item)
            btn.setProperty("class", "navBtn")
            sidebar_layout.addWidget(btn)
            
        sidebar_layout.addStretch()
        self.main_layout.addWidget(self.sidebar)
        
    def init_chat_area(self):
        chat_container = QWidget()
        self.chat_layout = QVBoxLayout(chat_container)
        self.chat_layout.setContentsMargins(40, 30, 40, 30)
        
        # Header
        header = QHBoxLayout()
        greeting = QLabel("Good Evening 👋\nHow can I help today?")
        greeting.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        header.addWidget(greeting)
        header.addStretch()
        
        # Mode Toggle Placeholder
        self.toggle_btn = QPushButton("🎤 Voice Mode")
        self.toggle_btn.setStyleSheet("background-color: rgba(255,255,255,0.1); color: white; padding: 8px 16px; border-radius: 16px;")
        header.addWidget(self.toggle_btn)
        self.chat_layout.addLayout(header)
        
        # Scroll Area for Chat Bubbles
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(20)
        self.scroll_area.setWidget(self.scroll_content)
        self.chat_layout.addWidget(self.scroll_area)
        
        # Input Bar
        input_frame = QFrame()
        input_frame.setObjectName("inputContainer")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 5, 10, 5)
        
        attach_btn = QPushButton("📎")
        attach_btn.setProperty("class", "iconBtn")
        attach_btn.setFixedWidth(40)
        
        self.input_box = QLineEdit()
        self.input_box.setObjectName("chatInput")
        self.input_box.setPlaceholderText("Ask HIRA anything...")
        self.input_box.returnPressed.connect(self.send_message)
        
        send_btn = QPushButton("➤")
        send_btn.setProperty("class", "iconBtn")
        send_btn.setObjectName("sendBtn")
        send_btn.setFixedWidth(40)
        send_btn.clicked.connect(self.send_message)
        
        input_layout.addWidget(attach_btn)
        input_layout.addWidget(self.input_box)
        input_layout.addWidget(send_btn)
        
        self.chat_layout.addWidget(input_frame)
        self.main_layout.addWidget(chat_container, stretch=1)
        
    def init_status_panel(self):
        self.status_panel = QFrame()
        self.status_panel.setObjectName("statusPanel")
        self.status_panel.setFixedWidth(280)
        status_layout = QVBoxLayout(self.status_panel)
        status_layout.setContentsMargins(20, 30, 20, 20)
        status_layout.setSpacing(15)
        
        header = QLabel("SYSTEM STATUS")
        header.setProperty("class", "statusHeader")
        status_layout.addWidget(header)
        
        card = QFrame()
        card.setProperty("class", "statusCard")
        card_layout = QVBoxLayout(card)
        
        self.cpu_label = QLabel("CPU: --%")
        self.ram_label = QLabel("RAM: --%")
        self.cpu_label.setProperty("class", "statusText")
        self.ram_label.setProperty("class", "statusText")
        
        card_layout.addWidget(self.cpu_label)
        card_layout.addWidget(self.ram_label)
        status_layout.addWidget(card)
        
        status_layout.addStretch()
        self.main_layout.addWidget(self.status_panel)
        
        # Start timer for status updates
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)
        self.update_status()

    def update_status(self):
        self.cpu_label.setText(f"CPU: {psutil.cpu_percent()}%")
        self.ram_label.setText(f"RAM: {psutil.virtual_memory().percent}%")

    def add_bubble(self, text, is_user=False):
        bubble = ChatBubble(text, is_user)
        # Wrap in QHBoxLayout to align left/right
        wrap_layout = QHBoxLayout()
        if is_user:
            wrap_layout.addStretch()
            wrap_layout.addWidget(bubble, stretch=3)
        else:
            wrap_layout.addWidget(bubble, stretch=3)
            wrap_layout.addStretch()
            
        wrap_widget = QWidget()
        wrap_widget.setLayout(wrap_layout)
        self.scroll_layout.addWidget(wrap_widget)
        
        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
        return bubble
        
    def send_message(self):
        text = self.input_box.text().strip()
        if text:
            self.add_bubble(text, is_user=True)
            self.input_box.clear()
            self.input_box.setEnabled(False)
            
            # Start streaming response
            self.current_bubble = self.add_bubble("", is_user=False)
            self.worker = AIStreamWorker(text)
            self.worker.token_received.connect(self.on_token_received)
            self.worker.stream_finished.connect(self.on_stream_finished)
            self.worker.error_occurred.connect(self.on_stream_error)
            self.worker.start()
            
    def on_token_received(self, chunk):
        if self.current_bubble:
            self.current_bubble.append_text(chunk)
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
            
    def on_stream_finished(self):
        self.input_box.setEnabled(True)
        self.input_box.setFocus()
        self.current_bubble = None
        
    def on_stream_error(self, err):
        if self.current_bubble:
            self.current_bubble.append_text(f"\n**Error:** {err}")
        self.input_box.setEnabled(True)
        self.current_bubble = None

def run_native_gui(process_command_func):
    app = QApplication(sys.argv)
    window = HiraMainWindow(process_command_func)
    window.show()
    sys.exit(app.exec())
