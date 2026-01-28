from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QLineEdit, QFileDialog, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import os
import quiz_generator

class QuizWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, questions, output_path):
        super().__init__()
        self.questions = questions
        self.output_path = output_path

    def run(self):
        try:
            quiz_generator.generate_quiz_video(self.questions, self.output_path)
            self.finished.emit(f"Saved to {self.output_path}")
        except Exception as e:
            self.error.emit(str(e))

class QuizGeneratorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        layout.addWidget(QLabel("<h2>Quiz Video Generator</h2>"))
        layout.addWidget(QLabel("Enter questions below (one per line, format: Question | Answer)"))

        # Question Input
        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("What is the capital of France? | Paris\nWho is the president of USA? | Joe Biden")
        layout.addWidget(self.text_area)

        # Output Selection
        out_layout = QHBoxLayout()
        self.out_path = QLineEdit("quiz_output.mp4")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_output)
        out_layout.addWidget(QLabel("Output:"))
        out_layout.addWidget(self.out_path)
        out_layout.addWidget(browse_btn)
        layout.addLayout(out_layout)

        # Generate Button
        self.gen_btn = QPushButton("Generate Quiz Video")
        self.gen_btn.clicked.connect(self.start_generation)
        self.gen_btn.setStyleSheet("background-color: #00acc1; color: white; padding: 10px; font-weight: bold;")
        layout.addWidget(self.gen_btn)

        # Status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Video", "", "MP4 Files (*.mp4)")
        if path:
            self.out_path.setText(path)

    def start_generation(self):
        text = self.text_area.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Please enter some questions!")
            return

        questions = []
        for line in text.split('\n'):
            if '|' in line:
                q, a = line.split('|', 1)
                questions.append({'q': q.strip(), 'a': a.strip()})
        
        if not questions:
            QMessageBox.warning(self, "Error", "No valid questions found. Use format: Question | Answer")
            return

        output_path = self.out_path.text()
        
        self.gen_btn.setEnabled(False)
        self.status_label.setText("Generating... Please wait.")
        
        self.worker = QuizWorker(questions, output_path)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, msg):
        self.gen_btn.setEnabled(True)
        self.status_label.setText("Done!")
        QMessageBox.information(self, "Success", msg)

    def on_error(self, err):
        self.gen_btn.setEnabled(True)
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, "Error", f"Generation failed: {err}")
