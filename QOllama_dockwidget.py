# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QOllamaDockWidget
                                 A QGIS plugin
 QGIS Ollama
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2025-03-02
        git sha              : $Format:%H$
        copyright            : (C) 2025 by dsyou / elcomtech
        email                : dsyou20@gmail,com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, QSettings, Qt, QUrl
from qgis.core import QgsProject
from openai import OpenAI
from .rag_handler import RAGHandler
from qgis.PyQt.QtGui import QDesktopServices

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'QOllama_dockwidget_base.ui'))


class QOllamaDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(QOllamaDockWidget, self).__init__(parent)
        self.rag_handler = None
        self.chat_history = []
        self.api_key = None  # API 키 변수 추가
        self.current_pdf_path = None  # PDF 파일 경로 저장
        self.setup_ui()

    def setup_ui(self):
        # 메인 위젯 설정
        self.main_widget = QtWidgets.QWidget()
        self.setWidget(self.main_widget)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        
        # 탭 위젯 생성
        self.tab_widget = QtWidgets.QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # 채팅 탭 설정
        self.chat_tab = QtWidgets.QWidget()
        self.chat_layout = QtWidgets.QVBoxLayout()
        self.chat_tab.setLayout(self.chat_layout)
        
        # 레이어 선택 영역
        layer_widget = QtWidgets.QWidget()
        layer_layout = QtWidgets.QHBoxLayout()
        layer_widget.setLayout(layer_layout)
        
        self.layer_label = QtWidgets.QLabel("분석할 레이어:")
        self.layer_combo = QtWidgets.QComboBox()
        
        # 레이어 리로드 버튼 추가
        self.reload_button = QtWidgets.QPushButton()
        self.reload_button.setToolTip("레이어 목록 새로고침")
        # 새로고침 아이콘 설정
        self.reload_button.setIcon(QtGui.QIcon(":/images/themes/default/mActionRefresh.svg"))
        self.reload_button.setFixedSize(28, 28)  # 버튼 크기 조정
        
        # PDF 보기 버튼 추가
        self.view_pdf_button = QtWidgets.QPushButton()
        self.view_pdf_button.setToolTip("생성된 PDF 보기")
        self.view_pdf_button.setIcon(QtGui.QIcon(":/images/themes/default/mActionFileOpen.svg"))
        self.view_pdf_button.setFixedSize(28, 28)
        self.view_pdf_button.setEnabled(False)  # 초기에는 비활성화
        
        self.process_button = QtWidgets.QPushButton("레이어 처리")
        
        layer_layout.addWidget(self.layer_label)
        layer_layout.addWidget(self.layer_combo)
        layer_layout.addWidget(self.reload_button)
        layer_layout.addWidget(self.view_pdf_button)
        layer_layout.addWidget(self.process_button)
        
        self.chat_layout.addWidget(layer_widget)
        
        # 채팅 표시 영역
        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(300)
        # 스타일 설정
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-family: Arial;
                font-size: 12px;
            }
        """)
        self.chat_layout.addWidget(self.chat_display)
        
        # 입력 영역
        input_widget = QtWidgets.QWidget()
        input_layout = QtWidgets.QHBoxLayout()
        input_widget.setLayout(input_layout)
        
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("메시지를 입력하세요...")
        self.send_button = QtWidgets.QPushButton("전송")
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        
        self.chat_layout.addWidget(input_widget)
        
        # 프로그레스바
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        self.chat_layout.addWidget(self.progress_bar)
        
        # 탭 추가
        self.tab_widget.addTab(self.chat_tab, "채팅")
        
        # 설정 탭
        self.setup_settings_tab()
        
        # 시그널 연결
        self.process_button.clicked.connect(self.process_current_layer)
        self.reload_button.clicked.connect(self.reload_layers)  # 리로드 버튼 시그널 연결
        self.view_pdf_button.clicked.connect(self.open_pdf)
        self.send_button.clicked.connect(self.send_message)
        self.input_field.returnPressed.connect(self.send_message)
        
        # 초기 레이어 목록 로드
        self.update_layer_list()

    def add_message(self, sender, message):
        """채팅 메시지 추가"""
        if sender == "AI":
            color = "#2E86C1"  # 파란색
            prefix = "[AI]"
        else:
            color = "#28B463"  # 초록색
            prefix = "[QGIS]"
            
        # HTML 이스케이프 처리
        message = message.replace("<", "&lt;").replace(">", "&gt;")
        html_message = f'<p><span style="color: {color}; font-weight: bold;">{prefix}</span> {message}</p>'
        self.chat_display.append(html_message)
        
        # 스크롤을 항상 아래로
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def send_message(self):
        """메시지 전송"""
        try:
            message = self.input_field.text().strip()
            if not message:
                return
                
            if not self.api_key:
                self.add_message("AI", "API 키를 먼저 설정해주세요.")
                return
                
            if not self.rag_handler:
                self.add_message("AI", "레이어를 먼저 처리해주세요.")
                return
                
            # 사용자 메시지 표시
            self.add_message("QGIS", message)
            self.input_field.clear()
            
            # 입력 필드와 전송 버튼 비활성화
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)
            
            try:
                # AI 응답 생성
                response = self.rag_handler.get_response(message)
                self.add_message("AI", response)
                
            except Exception as e:
                self.add_message("AI", f"응답 생성 중 오류가 발생했습니다: {str(e)}")
                
            finally:
                # 입력 필드와 전송 버튼 다시 활성화
                self.input_field.setEnabled(True)
                self.send_button.setEnabled(True)
                self.input_field.setFocus()
                
        except Exception as e:
            self.add_message("AI", f"메시지 처리 중 오류가 발생했습니다: {str(e)}")

    def process_current_layer(self):
        """현재 선택된 레이어 처리"""
        if not self.api_key:
            self.add_message("AI", "API 키를 먼저 설정해주세요.")
            return
            
        layer = self.layer_combo.currentData()
        if not layer:
            self.add_message("AI", "레이어를 선택해주세요.")
            return
            
        # 이전 PDF 파일 삭제
        if self.current_pdf_path and os.path.exists(self.current_pdf_path):
            try:
                os.remove(self.current_pdf_path)
            except:
                pass
            
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # RAG 핸들러 초기화
            self.rag_handler = RAGHandler(self.api_key)
            
            # 레이어 처리 및 PDF 경로 저장
            self.progress_bar.setValue(50)
            self.current_pdf_path = self.rag_handler.process_layer(layer)
            
            self.progress_bar.setValue(100)
            self.add_message("AI", f"'{layer.name()}' 레이어 처리가 완료되었습니다. 질문해 주세요!")
            
            # PDF 보기 버튼 활성화
            self.view_pdf_button.setEnabled(True)
            
        except Exception as e:
            self.add_message("AI", f"레이어 처리 중 오류가 발생했습니다: {str(e)}")
            self.view_pdf_button.setEnabled(False)
            self.current_pdf_path = None
        finally:
            self.progress_bar.setVisible(False)

    def setup_settings_tab(self):
        """설정 탭 설정"""
        self.settings_tab = QtWidgets.QWidget()
        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_tab.setLayout(self.settings_layout)
        
        # API 키 설정
        self.api_key_label = QtWidgets.QLabel("ChatGPT API 키:")
        self.api_key_input = QtWidgets.QLineEdit()
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        
        self.save_button = QtWidgets.QPushButton("저장")
        self.save_button.clicked.connect(self.save_api_key)
        
        self.settings_layout.addWidget(self.api_key_label)
        self.settings_layout.addWidget(self.api_key_input)
        self.settings_layout.addWidget(self.save_button)
        self.settings_layout.addStretch()
        
        self.tab_widget.addTab(self.settings_tab, "설정")
        
        # 저장된 API 키 로드
        self.load_api_key()

    def reload_layers(self):
        """레이어 목록 새로고침"""
        try:
            # 현재 선택된 레이어 이름 저장
            current_layer_name = self.layer_combo.currentText()
            
            # 레이어 목록 업데이트
            self.update_layer_list()
            
            # 이전에 선택했던 레이어 다시 선택
            index = self.layer_combo.findText(current_layer_name)
            if index >= 0:
                self.layer_combo.setCurrentIndex(index)
            
            # 성공 메시지 표시
            self.add_message("AI", "레이어 목록이 업데이트되었습니다.")
            
        except Exception as e:
            self.add_message("AI", f"레이어 목록 업데이트 중 오류가 발생했습니다: {str(e)}")

    def update_layer_list(self):
        """레이어 콤보박스 업데이트"""
        self.layer_combo.clear()
        layers = QgsProject.instance().mapLayers().values()
        
        # 벡터 레이어만 필터링하여 정렬된 목록 생성
        vector_layers = [(layer.name(), layer) for layer in layers if layer.type().name == 'VectorLayer']
        vector_layers.sort(key=lambda x: x[0].lower())  # 이름으로 정렬
        
        # 정렬된 레이어 추가
        for name, layer in vector_layers:
            self.layer_combo.addItem(name, layer)
            
        # 레이어가 없는 경우 메시지 표시
        if self.layer_combo.count() == 0:
            self.add_message("AI", "프로젝트에 벡터 레이어가 없습니다. 레이어를 추가해주세요.")

    def save_api_key(self):
        """API 키 저장"""
        api_key = self.api_key_input.text().strip()
        if api_key:
            settings = QSettings()
            settings.setValue("QOllama/api_key", api_key)
            self.api_key = api_key  # API 키 저장
            self.add_message("AI", "API 키가 저장되었습니다.")
        else:
            self.add_message("AI", "API 키를 입력해주세요.")

    def load_api_key(self):
        """저장된 API 키 로드"""
        settings = QSettings()
        self.api_key = settings.value("QOllama/api_key", "")
        self.api_key_input.setText(self.api_key)

    def open_pdf(self):
        """PDF 파일 열기"""
        if self.current_pdf_path and os.path.exists(self.current_pdf_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_pdf_path))
        else:
            self.add_message("AI", "PDF 파일을 찾을 수 없습니다.")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
