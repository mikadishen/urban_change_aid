from PyQt5.QtCore import QTimer  # Adicione isso no top, após imports Qt
from PyQt5.QtWidgets import (QLabel, QTabWidget, QWidget, QVBoxLayout,
                             QHBoxLayout, QSlider, QSpinBox, QDoubleSpinBox, QPushButton, QDialog, QGridLayout, QScrollArea, QComboBox)
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QApplication
from datetime import datetime
from qgis.PyQt.QtGui import QTextCursor
from qgis.PyQt.QtWidgets import QTextEdit
import shutil
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import cv2
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from scipy import ndimage as ndi
from qgis.utils import iface
from osgeo import gdal
import numpy as np
import os
from qgis import processing
from qgis.gui import QgsMapCanvas, QgsMapLayerComboBox
from qgis.core import (
    QgsRasterLayer, QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField,
    QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer,
    QgsRectangle, QgsCoordinateReferenceSystem, QgsPointXY, Qgis, QgsMapLayer,
    QgsVectorFileWriter, QgsMessageLog, QgsSingleBandGrayRenderer, QgsWkbTypes, QgsApplication)

from qgis.core import QgsDistanceArea, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QVariant, Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QSlider, QRadioButton, QSpinBox, QGroupBox, QCheckBox
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.core import QgsProcessingAlgorithm
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiPolygon,
    Polygon,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from scipy.optimize import brentq
from shapely import make_valid
# Importa o carregador WKT da Shapely
from shapely.wkt import loads as shapely_loads
import numpy as np
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingProvider
SAFE_NO_REMOVE_LAYERS = True


class UrbanChangeAid:
    """QGIS Plugin for Urban Change Detection."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.log_message("Plugin directory: {}".format(self.plugin_dir))

        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'UrbanChangeAid_{}.qm'.format(locale))
        self.log_message("Locale path: {}".format(locale_path))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
            self.log_message("Translator loaded successfully.")
        else:
            self.log_message("Locale file not found: {}".format(locale_path))

        self.actions = []
        self.menu = self.tr(u'&Urban Change Aid')
        self.log_message("Menu initialized: {}".format(self.menu))

        self.first_start = None
        self.dialog = None
        self.loaded_layer_ids = []
        self.monitoring_year = None  # Track which year is being georeferenced
        self.layer_count_before = 0  # Track layer count before georeferencing
        self.log_message("Initial attributes set.")

        self.temp_dir = os.path.join(self.plugin_dir, 'temp')
        self.log_message("Temp directory: {}".format(self.temp_dir))
        if not os.path.exists(self.temp_dir):
            try:
                os.makedirs(self.temp_dir)
                self.log_message("Temp directory created.")
            except OSError as e:
                self.log_message(
                    "Failed to create temp directory: {}".format(e))
                QgsMessageLog.logMessage(
                    f"Failed to create temp directory: {e}", 'UrbanChangeAid', Qgis.Warning)

        self.reset_plugin_state(silent=True)
        self.log_message("Plugin state reset.")

        self.register_sieve_algorithm()
        self.log_message("Sieve algorithm registered.")

        # NOTE: Removed defensive stub for `export_all_results` that could
        # unintentionally shadow the real implementation defined later in
        # this class. The real method is declared further below and should
        # be used by UI signal connections.

    def register_sieve_algorithm(self):
        """Temporarily disabled until UrbanChangeAidProvider is implemented."""
        QgsMessageLog.logMessage(
            "register_sieve_algorithm skipped (UrbanChangeAidProvider not implemented).",
            'UrbanChangeAid', Qgis.Info
        )

    def reset_plugin_state(self, silent=False):
        if hasattr(self, 'temp_dir') and self.temp_dir:
            if os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                    os.makedirs(self.temp_dir)
                except OSError as e:
                    if not silent:
                        self.iface.messageBar().pushMessage(
                            "Warning", f"Could not reset temp directory: {e}", level=Qgis.Warning)
        else:
            self.temp_dir = r"C:\Temp\urban_change_aid"
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)

        self.year1_path = None
        self.year2_path = None
        self.aligned_year1_path = None
        self.aligned_year2_path = None
        self.band_year1_path = None
        self.band_year2_path = None
        self.norm_year1_path = None
        self.norm_year2_path = None
        self.bin_year1_path = None
        self.bin_year2_path = None
        self.difference_path = None  # Adicione esta linha aqui
        self.gain_mask_path = None
        self.loss_mask_path = None
        self.gain_vector_path = None
        self.loss_vector_path = None
        self.filtered_gain_vector = None
        self.filtered_loss_vector = None
        # path for centroids generated for export/analysis
        self.export_centroids_path = None
        self.smoothed_gain_vector_path = None
        self.smoothed_loss_vector_path = None
        self.selected_crop_bounds = None

        self.selected_layer = None
        self.selected_field = None
        self.selected_old_value = None
        self.selected_new_value = None
        self.change_date = None
        self.selected_features = []
        self.changes_detected = False
        self.undo_stack = []
        self.redo_stack = []
        self.analysis_results = {}
        self.original_layer_state = None
        self.layer_snapshots = {}
        self.last_analysis_time = None
        self.custom_rules = {}
        self.visualization_layer = None
        self.report_path = None
        self.export_format = 'pdf'
        self.user_feedback = []
        self.plugin_version = '1.0.0'

        if self.loaded_layer_ids:
            if not SAFE_NO_REMOVE_LAYERS:
                try:
                    QgsProject.instance().removeMapLayers(self.loaded_layer_ids)
                except Exception as _e:
                    QgsMessageLog.logMessage(
                        f"Error removing plugin layers: {_e}", 'UrbanChangeAid', Qgis.Warning)
            # clear the list regardless to avoid dangling references
            self.loaded_layer_ids = []

    def tr(self, message):
        return QCoreApplication.translate('UrbanChangeAid', message)


    def generate_heatmaps(self):
        """Gera heatmaps a partir do vetor de perda suavizado (se disponível) ou de qualquer camada de pontos carregada no projeto, com escolha do usuário."""
        try:
            # 1. Busca todas as camadas de pontos (vetoriais) no projeto
            # A verificação de geometria é feita de forma mais robusta para incluir camadas que podem ter QgsWkbTypes.Unknown
            # mas que são de fato pontos (como as recém-criadas).
            point_layers = []
            for layer in QgsProject.instance().mapLayers().values():
                if layer.type() == QgsMapLayer.VectorLayer:
                    # Verifica se é Point ou se é Unknown/NoGeometry mas tem um provedor de dados
                    # A verificação mais robusta é: se for Point, ou se for Unknown mas tiver um provedor de dados (o que sugere que é um layer válido)
                    geom_type = layer.geometryType()
                    if geom_type == QgsWkbTypes.Point or geom_type == QgsWkbTypes.PointZ or geom_type == QgsWkbTypes.PointM or geom_type == QgsWkbTypes.PointZM:
                        point_layers.append(layer)
                    elif geom_type == QgsWkbTypes.Unknown and layer.dataProvider() is not None:
                        # Tenta inferir o tipo de geometria se for Unknown (pode ser um layer temporário)
                        # No entanto, para Heatmap, é crucial que seja Point. Vamos manter a verificação estrita,
                        # mas garantindo que todos os tipos de Point sejam considerados.
                        # A falha pode estar na inicialização do layer.
                        # Vamos manter a checagem estrita, mas o problema pode ser que os layers do usuário não são Point, mas sim MultiPoint,
                        # ou o QGIS não está reconhecendo o tipo WKB.
                        # O mais provável é que os layers do usuário sejam MultiPoint.
                        if layer.wkbType() in [QgsWkbTypes.MultiPoint, QgsWkbTypes.MultiPointZ, QgsWkbTypes.MultiPointM, QgsWkbTypes.MultiPointZM]:
                            point_layers.append(layer)
                        # Se o layer for Point ou MultiPoint, ele é adicionado.
                        elif geom_type == QgsWkbTypes.Unknown:
                            # Se for Unknown, vamos inspecionar a primeira feature para ver se é Point.
                            try:
                                first_feature = next(layer.getFeatures())
                                if first_feature.geometry().wkbType() in [QgsWkbTypes.Point, QgsWkbTypes.PointZ, QgsWkbTypes.PointM, QgsWkbTypes.PointZM, QgsWkbTypes.MultiPoint, QgsWkbTypes.MultiPointZ, QgsWkbTypes.MultiPointM, QgsWkbTypes.MultiPointZM]:
                                    point_layers.append(layer)
                            except StopIteration:
                                # Layer vazio, ignora
                                pass
                            except Exception:
                                # Erro ao ler feature, ignora
                                pass
            
            # Remove duplicatas e layers inválidos
            point_layers = list(set(point_layers))
            point_layers = [layer for layer in point_layers if layer.isValid()]

            # Adiciona o vetor de perda suavizado (se existir) à lista de camadas disponíveis, se ainda não estiver no projeto
            smoothed_loss_layer = None
            if self.smoothed_loss_vector_path and os.path.exists(self.smoothed_loss_vector_path):
                # Cria uma referência temporária para o layer
                smoothed_loss_layer = QgsVectorLayer(
                    self.smoothed_loss_vector_path, "Centroids Loss Smoothed (Auto)", "ogr")
                
                # Verifica se o layer já está na lista (pelo nome ou fonte)
                is_already_in_project = any(
                    layer.source() == smoothed_loss_layer.source() for layer in point_layers)
                
                if smoothed_loss_layer.isValid() and smoothed_loss_layer.geometryType() == QgsWkbTypes.Point and not is_already_in_project:
                    # Adiciona o layer temporário para que o usuário possa selecioná-lo
                    point_layers.insert(0, smoothed_loss_layer)
                    self.log_message("Added smoothed loss vector to selection list.")
                elif is_already_in_project:
                    # Se já estiver no projeto, apenas o encontra para pré-seleção
                    smoothed_loss_layer = next((layer for layer in point_layers if layer.source() == smoothed_loss_layer.source()), None)

            if not point_layers:
                QMessageBox.warning(self.dialog, "Warning",
                                    "No point vector layers found in the project. Load a centroid layer first.")
                self.log_message("No point layers found for heatmap generation.")
                return

            # 2. Diálogo para seleção da camada e parâmetros
            from qgis.PyQt.QtWidgets import QDialogButtonBox, QComboBox, QDoubleSpinBox, QLabel, QVBoxLayout, QHBoxLayout
            choice_dlg = QDialog(self.dialog)
            choice_dlg.setWindowTitle("Generate Heatmap from Centroids")
            choice_layout = QVBoxLayout(choice_dlg)

            # Seletor de Camada
            layer_box = QHBoxLayout()
            layer_lbl = QLabel("Select Centroid Layer:")
            layer_combo = QComboBox()
            
            # Variável para rastrear o índice do layer de perda suavizado para pré-seleção
            pre_select_index = -1
            
            for i, layer in enumerate(point_layers):
                layer_combo.addItem(layer.name(), layer)
                # Usa a fonte para garantir que o layer de perda suavizado seja pré-selecionado
                if smoothed_loss_layer and layer.source() == smoothed_loss_layer.source():
                    pre_select_index = i
            
            if pre_select_index != -1:
                layer_combo.setCurrentIndex(pre_select_index)

            layer_box.addWidget(layer_lbl)
            layer_box.addWidget(layer_combo)
            choice_layout.addLayout(layer_box)

            # Raio
            radius_box = QHBoxLayout()
            radius_lbl = QLabel("Kernel Radius (map units, e.g., meters):")
            radius_spin = QDoubleSpinBox()
            radius_spin.setRange(1, 100000)
            radius_spin.setValue(1000)
            radius_spin.setSingleStep(100)
            radius_box.addWidget(radius_lbl)
            radius_box.addWidget(radius_spin)
            choice_layout.addLayout(radius_box)

            # Botões OK/Cancel
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Generate Heatmap")
            cancel_btn = QPushButton("Cancel")
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            choice_layout.addLayout(btn_layout)

            def generate_selected():
                selected_layer = layer_combo.currentData()
                radius = radius_spin.value()

                if not selected_layer:
                    QMessageBox.warning(choice_dlg, "Warning", "Please select a layer.")
                    return

                if selected_layer.featureCount() == 0:
                    QMessageBox.warning(choice_dlg, "Warning", f"Layer '{selected_layer.name()}' has no features.")
                    return

                try:
                    # Define o caminho de saída
                    layer_name_safe = selected_layer.name().replace(' ', '_').replace('/', '_')
                    heatmap_path = os.path.join(
                        self.temp_dir, f"{layer_name_safe}_heatmap.tif")

                    # Parâmetros do algoritmo de Heatmap
                    params = {
                        'INPUT': selected_layer,
                        'RADIUS': radius,
                        'PIXEL_SIZE': 10,  # Ajuste para resolução desejada
                        'KERNEL': 0,  # Quartic (default)
                        'OUTPUT': heatmap_path
                    }

                    # Executa o processamento
                    result = processing.run(
                        "qgis:heatmapkerneldensityestimation", params)
                    out_path = result.get('OUTPUT') or result.get(
                        'OUTPUT_RASTER') or result.get('OUTPUT_LAYER')

                    if out_path:
                        # Carrega o resultado no projeto
                        heatmap_layer = QgsRasterLayer(
                            out_path, f"Heatmap - {selected_layer.name()}")
                        if heatmap_layer.isValid():
                            QgsProject.instance().addMapLayer(heatmap_layer)
                            self.log_message(
                                f"✅ Heatmap generated from '{selected_layer.name()}' ({radius}m radius) and loaded in project.")
                            QMessageBox.information(
                                self.dialog, "Success", f"Heatmap generated and loaded from '{selected_layer.name()}'.")
                        else:
                            self.log_message(
                                "Warning: Invalid Heatmap layer.")
                            QMessageBox.warning(
                                self.dialog, "Error", "Failed to load generated Heatmap layer.")
                    else:
                        self.log_message("Error: Heatmap algorithm did not return an output path.")
                        QMessageBox.warning(
                            self.dialog, "Error", "Heatmap generation failed.")

                    choice_dlg.accept()

                except Exception as e:
                    self.log_message(f"Error generating heatmap: {str(e)}")
                    QMessageBox.warning(self.dialog, "Error",
                                        f"Error generating heatmap: {str(e)}")

            ok_btn.clicked.connect(generate_selected)
            cancel_btn.clicked.connect(choice_dlg.reject)
            
            choice_dlg.exec_()

        except Exception as e:
            self.log_message(f"Error in generate_heatmaps: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error generating heatmaps: {str(e)}")


    def _safe_layer_source(self, layer: QgsVectorLayer) -> str:
        try:
            src = layer.source()
            if '|' in src:
                src = src.split('|')[0]
            return src
        except Exception:
            return ''

    def export_all_results(self):
        """Exporta todos os resultados do diretório temporário para um diretório escolhido, com opção de selecionar o que salvar."""
        export_dir = QFileDialog.getExistingDirectory(
            self.dialog, "Select Output Directory for All Results")
        if not export_dir:
            return

        try:
            # Lista todos os arquivos no temp_dir (filtros para .shp, .tif, etc.)
            files_in_temp = [f for f in os.listdir(
                self.temp_dir) if os.path.isfile(os.path.join(self.temp_dir, f))]
            if not files_in_temp:
                self.log_message("No files found in temp directory to export.")
                QMessageBox.information(
                    self.dialog, "Info", "No files available in temp directory.")
                return

            # Cria dialog para seleção (com checkboxes)
            select_dlg = QDialog(self.dialog)
            select_dlg.setWindowTitle("Select Files to Export")
            # ← FIX: Modal pra não sumir ao clicar fora, bloqueia só o parent
            select_dlg.setWindowModality(Qt.WindowModal)
            select_dlg.resize(800, 400)  # ← NOVO: Tamanho maior pra não cortar
            select_layout = QVBoxLayout(select_dlg)

            # Grupo com checkboxes em grid horizontal (pra não cortar vertical)
            group_box = QGroupBox("Select files from temp:")
            # ← FIX: QGridLayout pra disposição horizontal (3 colunas, ajustável)
            group_layout = QGridLayout(group_box)
            checkboxes = []
            num_columns = 3  # Colunas pra wrap horizontal
            for i, file in enumerate(files_in_temp):
                chk = QCheckBox(file)
                chk.setChecked(True)  # Todos selecionados por default
                row = i // num_columns
                col = i % num_columns
                group_layout.addWidget(chk, row, col)
                checkboxes.append(chk)

            # Scroll se muitos arquivos
            scroll_area = QScrollArea()
            scroll_area.setWidget(group_box)
            scroll_area.setWidgetResizable(True)
            select_layout.addWidget(scroll_area)

            # Botões OK/Cancel
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Export Selected")
            cancel_btn = QPushButton("Cancel")
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            select_layout.addLayout(btn_layout)

            def export_selected():
                selected_files = [chk.text()
                                  for chk in checkboxes if chk.isChecked()]
                if not selected_files:
                    QMessageBox.warning(
                        select_dlg, "Warning", "No files selected.")
                    return

                exported_count = 0
                for file in selected_files:
                    src_path = os.path.join(self.temp_dir, file)
                    dest_path = os.path.join(export_dir, file)
                    try:
                        # Copia o arquivo (simples, pra qualquer tipo)
                        shutil.copy(src_path, dest_path)
                        self.log_message(f"Exported {file} to {dest_path}")
                        exported_count += 1
                    except Exception as copy_e:
                        self.log_message(
                            f"Error copying {file}: {str(copy_e)}")

                self.log_message(
                    f"All selected results ({exported_count}) exported successfully.")
                QMessageBox.information(
                    self.dialog, "Success", f"Selected files exported to {export_dir}")
                select_dlg.accept()

            ok_btn.clicked.connect(export_selected)
            cancel_btn.clicked.connect(select_dlg.reject)

            select_dlg.exec_()  # Modal exec pra ficar aberto até OK/Cancel

        except Exception as e:
            self.log_message(f"Error exporting all results: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error exporting all results: {str(e)}")


    def initGui(self):
        icon_path = os.path.join(
            self.plugin_dir, "icons", "urban_icon_house.png")
        self.action = QAction(
            QIcon(icon_path), "Urban Change Detection Aid", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Urban Change Detection Aid", self.action)

    def unload(self):
        self.iface.removePluginMenu("&Urban Change Detection Aid", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dialog is None:
            ui_path = os.path.join(self.plugin_dir, "forms", "main.ui")
            try:
                self.dialog = uic.loadUi(ui_path)

                # REMOVIDO: Código de adição dinâmica do botão de heatmap para resolver a duplicação.
                # O botão de heatmap deve ser definido no .ui e conectado a self.generate_heatmaps.

                # preenche combos com camadas vetoriais já no projeto (se houver)
                # self.populate_vector_combos()

                # 👉 mover para cá os findChild e conexões
                self.generate_gain_loss_button = self.dialog.findChild(
                    QPushButton, "generateMasks")
                if self.generate_gain_loss_button:
                    self.generate_gain_loss_button.clicked.connect(
                        self.on_generate_gain_loss_clicked)
                else:
                    QMessageBox.warning(
                        self.dialog, "Error", "Button 'Generate Masks' not found in the UI.")

                # logTextEdit
                if hasattr(self.dialog, 'logTextEdit'):
                    self.log_text = self.dialog.logTextEdit
                else:
                    self.log_text = QTextEdit(self.dialog)
                    main_layout = self.dialog.layout()
                    if main_layout:
                        main_layout.addWidget(QLabel("Log:"))
                        main_layout.addWidget(self.log_text)

                # top layout com botões
                top_layout = QHBoxLayout()
                self.minimize_button = QPushButton("Minimize", self.dialog)
                self.minimize_button.clicked.connect(
                    lambda: self.dialog.showMinimized())
                top_layout.addWidget(self.minimize_button)

                self.help_button = QPushButton("Help", self.dialog)
                self.help_button.clicked.connect(self.show_help)
                top_layout.addWidget(self.help_button)

                top_layout.addStretch()
                main_layout = self.dialog.layout()
                if main_layout:
                    main_layout.insertLayout(0, top_layout)

                self.log_message("Plugin started.")

            except Exception as e:
                QMessageBox.critical(
                    None, "Error", f"Failed to load UI: {str(e)}")
                return

            # Configurações iniciais dos spinbox
            self.dialog.spinCropWidth.setMaximum(99999)
            self.dialog.spinCropHeight.setMaximum(99999)
            
            # --- Ajuste para 16 bits na Binarização ---
            # A detecção do max_val deve ser feita aqui para definir o range dos spinboxes de threshold.
            # Como o self.band_yearX_path ainda não está definido, vamos usar uma função para obter o max_val
            # ou, se não for possível, usar 65535 como fallback para o range máximo.
            
            max_val_binarization = 255 # Default para 8 bits
            
            # Tenta detectar o max_val da imagem normalizada (se já existir)
            if self.norm_year1_path and os.path.exists(self.norm_year1_path):
                try:
                    ds1 = gdal.Open(self.band_year1_path)
                    band1 = ds1.GetRasterBand(1).ReadAsArray()
                    max_val_binarization = int(np.nanmax(band1))
                    ds1 = None
                except Exception:
                    max_val_binarization = 65535 # Fallback se a leitura falhar, assume 16 bits
            elif self.band_year1_path and os.path.exists(self.band_year1_path):
                # Se a normalizada não existe, tenta a banda original
                try:
                    ds1 = gdal.Open(self.band_year1_path)
                    band1 = ds1.GetRasterBand(1).ReadAsArray()
                    max_val_binarization = int(np.nanmax(band1))
                    ds1 = None
                except Exception:
                    max_val_binarization = 65535 # Fallback se a leitura falhar, assume 16 bits
            
            # Garante que o range seja 65535 se o valor detectado for maior que 255
            slider_max_binarization = 9999999 # Ajustado para permitir 7 caracteres numéricos (até 65535 e mais)
            
            if hasattr(self.dialog, 'spinThresholdYear1'):
                self.dialog.spinThresholdYear1.setMaximum(slider_max_binarization)
            if hasattr(self.dialog, 'spinThresholdYear2'):
                self.dialog.spinThresholdYear2.setMaximum(slider_max_binarization)
            # --- Fim do Ajuste para 16 bits na Binarização ---

            # Conecta sinais
            self.connect_signals()

            # Conexão do botão de Heatmap (Problema 1)
            # O botão deve ser conectado em connect_signals para evitar duplicação e garantir que o nome correto seja usado.
            # Este bloco é removido.

            # Conexão do botão Export All Results (Problema 2)
            export_btn = self.dialog.findChild(QPushButton, "export_all_results_btn")
            if export_btn:
                export_btn.clicked.connect(self.export_all_results)
                self.log_message("Connected 'Export All Results' button (export_all_results_btn).")
            else:
                self.log_message("Warning: 'export_all_results_btn' not found in UI for connection.")

            if hasattr(self.dialog, 'previewBandsButton'):
                self.dialog.previewBandsButton.clicked.connect(
                    self.open_band_preview_dialog)
            if hasattr(self.dialog, 'openHistogramButton'):
                self.dialog.openHistogramButton.setVisible(False)
            if hasattr(self.dialog, 'nextToSieve'):
                self.dialog.nextToSieve.clicked.connect(self.next_to_sieve)

            # Cria a aba Smoothify (será inserida na posição 9)
                # Cria a nova aba Orthogonalize & Simplify (índice 8)
                self.create_orthogonalize_tab()
                # Cria a aba Smoothify (índice 9)
                self.create_smoothify_tab()

            # Desabilita todas as abas, exceto a primeira (Input Images)
            for i in range(1, self.dialog.tabWidget.count()):
                self.dialog.tabWidget.setTabEnabled(i, False)

            self.populate_project_layers()

        # sempre mostra a janela no final
        self.dialog.show()

    def create_smoothify_tab(self):
        """Cria e insere a nova aba Smoothify na posição 9."""
        tab_smoothify = QWidget()
        tab_smoothify.setObjectName("tabSmoothify")
        tab_smoothify.setWindowTitle("Smoothify")

        layout = QVBoxLayout(tab_smoothify)

        # Parâmetros de Smoothify
        smooth_iterations_spin = QSpinBox()
        smooth_iterations_spin.setRange(1, 10)
        smooth_iterations_spin.setValue(3)
        smooth_iterations_spin.setObjectName("smoothIterationsSpin")

        segment_length_spin = QDoubleSpinBox()
        segment_length_spin.setRange(0.1, 100.0)
        segment_length_spin.setValue(1.0)
        segment_length_spin.setDecimals(2)
        segment_length_spin.setObjectName("segmentLengthSpin")

        preserve_area_check = QCheckBox("Preservar Área (Polygons)")
        preserve_area_check.setChecked(True)
        preserve_area_check.setObjectName("preserveAreaCheck")

        area_tolerance_spin = QDoubleSpinBox()
        area_tolerance_spin.setRange(0.001, 1.0)
        area_tolerance_spin.setValue(0.01)
        area_tolerance_spin.setDecimals(3)
        area_tolerance_spin.setObjectName("areaToleranceSpin")

        # Botão de processamento
        btn_smoothify = QPushButton("Apply Smoothify and Load Vectors")
        btn_smoothify.setObjectName("btnSmoothify")
        btn_smoothify.clicked.connect(self.apply_smoothify)

        # Layout de parâmetros
        param_layout = QGridLayout()
        param_layout.addWidget(
            QLabel("Iterações de Suavização (Chaikin):"), 0, 0)
        param_layout.addWidget(smooth_iterations_spin, 0, 1)

        param_layout.addWidget(QLabel("Comprimento do Segmento (Unidades de Mapa):"), 1, 0)
        param_layout.addWidget(segment_length_spin, 1, 1)
        param_layout.addWidget(preserve_area_check, 2, 0, 1, 2)
        param_layout.addWidget(QLabel("Tolerância de Área (%):"), 3, 0)
        param_layout.addWidget(area_tolerance_spin, 3, 1)

        layout.addLayout(param_layout)
        layout.addWidget(btn_smoothify)
        layout.addStretch()

        # Insere a aba na posição 10 (após Orthogonalize & Simplify, que é 9)
        self.dialog.tabWidget.insertTab(10, tab_smoothify, "Smoothify")

        # Adiciona botões de navegação
        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("Previous")
        next_btn = QPushButton("Next")
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(next_btn)
        layout.addLayout(nav_layout)

        # Conecta os botões de navegação: voltar para Orthogonalize e avançar para Centroids
        # Volta para Orthogonalize & Simplify (índice 9)
        prev_btn.clicked.connect(
            lambda: self.dialog.tabWidget.setCurrentIndex(9))
        # Avança para Centroid_Export (opcional)
        next_btn.clicked.connect(self.next_to_centroids)

    def create_orthogonalize_tab(self):
        """Cria e insere a nova aba Orthogonalize & Simplify na posição 9 (antes de Smoothify)."""
        tab_ortho = QWidget()
        tab_ortho.setObjectName("tabOrthogonalize")
        tab_ortho.setWindowTitle("Orthogonalize & Simplify")

        layout = QVBoxLayout(tab_ortho)

        # Descrição e Instruções
        desc_label = QLabel(
            "Use this tab to simplify or orthogonalize the filtered vectors (gain_filtered.shp and loss_filtered.shp) before applying Smoothify or generating Centroids.")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Componentes de UI para Orthogonalize/Simplify (baseado em on_orthogonalize_or_simplify_button_clicked)
        # Input Layer (ComboBox) - Será populado dinamicamente ou simplificado para usar os arquivos temporários
        # Por simplicidade, vamos usar um botão que abre o diálogo existente (que já tem a lógica de UI complexa)
        # e ajustamos o fluxo para que ele não feche o diálogo principal.

        # Botão para abrir o diálogo de Orthogonalize/Simplify
        btn_open_dialog = QPushButton("Open Simplify/Orthogonalize Dialog")
        btn_open_dialog.setObjectName("btnOpenOrthoDialog")
        # Conecta ao método que abre o diálogo (o método existente será renomeado/adaptado)
        btn_open_dialog.clicked.connect(
            self.on_orthogonalize_or_simplify_button_clicked)
        layout.addWidget(btn_open_dialog)

        # Insere a aba na posição 9 (após Metrics Filter, que é 8, se Vectorization for 7)
        # Assumindo que Metrics Filter é 8 e Vectorization é 7, a ordem correta é Vectorization(7) > Metrics_Filtering(8) > Ortogonalize_Simplify(9)
        self.dialog.tabWidget.insertTab(
            9, tab_ortho, "Orthogonalize & Simplify")

        # Adiciona botões de navegação
        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("Previous")
        next_btn = QPushButton("Next")
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(next_btn)
        layout.addLayout(nav_layout)

        # Conecta os botões
        # A aba anterior a 8 (Orthogonalize) é 7 (Metrics Filter)
        # Volta para Metrics Filter (índice 8)
        prev_btn.clicked.connect(
            lambda: self.dialog.tabWidget.setCurrentIndex(8))
        # Avança para Centroid_Export (opcional)
        next_btn.clicked.connect(self.next_to_centroids)

    def next_to_metrics_filter(self):
        """Avança para o próximo tab: Metrics Filter (movimenta relativo ao tab atual)."""
        try:
            tw = getattr(self.dialog, 'tabWidget', None)
            if not tw:
                return
            cur = tw.currentIndex()
            if cur + 1 < tw.count():
                tw.setTabEnabled(cur + 1, True)
                tw.setCurrentIndex(cur + 1)
                self.log_message(
                    f"➡️ Moved to Metrics Filter tab (index {cur+1}).")
        except Exception as e:
            self.log_message(f"Error advancing to Metrics Filter tab: {e}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {e}")
            except Exception:
                pass

    def next_to_orthogonalize(self):
        """Avança para a aba Orthogonalize & Simplify (relativo ao atual)."""
        try:
            tw = getattr(self.dialog, 'tabWidget', None)
            if not tw:
                return
            cur = tw.currentIndex()
            if cur + 1 < tw.count():
                tw.setTabEnabled(cur + 1, True)
                tw.setCurrentIndex(cur + 1)
                self.log_message(
                    f"➡️ Moved to Orthogonalize & Simplify tab (index {cur+1}).")
        except Exception as e:
            self.log_message(
                f"Error advancing to Orthogonalize & Simplify tab: {e}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {e}")
            except Exception:
                pass

    def next_to_smoothify(self):
        """Avança para a aba Smoothify (relativo ao atual). Verifica se existem vetores filtrados antes."""
        try:
            gain_exists = bool(getattr(self, 'filtered_gain_vector', None) and os.path.exists(
                getattr(self, 'filtered_gain_vector')))
            loss_exists = bool(getattr(self, 'filtered_loss_vector', None) and os.path.exists(
                getattr(self, 'filtered_loss_vector')))
            if not (gain_exists or loss_exists):
                QMessageBox.warning(
                    self.dialog, "Warning", "Please export filtered vectors (Gain/Loss) first or run Metrics Filter before Smoothify.")
                return

            tw = getattr(self.dialog, 'tabWidget', None)
            if not tw:
                return
            cur = tw.currentIndex()
            if cur + 1 < tw.count():
                tw.setTabEnabled(cur + 1, True)
                tw.setCurrentIndex(cur + 1)
                self.log_message(f"➡️ Moved to Smoothify tab (index {cur+1}).")
        except Exception as e:
            self.log_message(f"Error advancing to Smoothify tab: {e}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {e}")
            except Exception:
                pass

    def next_to_centroids(self):
        """Avança para a aba Centroids (relativo ao atual)."""
        try:
            tw = getattr(self.dialog, 'tabWidget', None)
            if not tw:
                return
            cur = tw.currentIndex()
            if cur + 1 < tw.count():
                tw.setTabEnabled(cur + 1, True)
                tw.setCurrentIndex(cur + 1)
                self.log_message(f"➡️ Moved to Centroids tab (index {cur+1}).")
        except Exception as e:
            self.log_message(f"Error advancing to Centroids tab: {e}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {e}")
            except Exception:
                pass

    def next_to_export(self):
        """Avança para a aba Export & Finish (relativo ao atual)."""
        try:
            tw = getattr(self.dialog, 'tabWidget', None)
            if not tw:
                return
            cur = tw.currentIndex()
            if cur + 1 < tw.count():
                tw.setTabEnabled(cur + 1, True)
                tw.setCurrentIndex(cur + 1)
                self.log_message(
                    f"➡️ Moved to Export & Finish tab (index {cur+1}).")
        except Exception as e:
            self.log_message(f"Error advancing to Export & Finish tab: {e}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {e}")
            except Exception:
                pass

    def next_to_smoothify(self):
        """Avança para a aba Smoothify (relativo ao atual). Verifica se existem vetores filtrados antes."""
        try:
            gain_exists = bool(getattr(self, 'filtered_gain_vector', None) and os.path.exists(
                getattr(self, 'filtered_gain_vector')))
            loss_exists = bool(getattr(self, 'filtered_loss_vector', None) and os.path.exists(
                getattr(self, 'filtered_loss_vector')))
            if not (gain_exists or loss_exists):
                QMessageBox.warning(
                    self.dialog, "Warning", "Please export filtered vectors (Gain/Loss) first or run Metrics Filter before Smoothify.")
                return

            tw = getattr(self.dialog, 'tabWidget', None)
            if not tw:
                return
            cur = tw.currentIndex()
            if cur + 1 < tw.count():
                tw.setTabEnabled(cur + 1, True)
                tw.setCurrentIndex(cur + 1)
                self.log_message(f"➡️ Moved to Smoothify tab (index {cur+1}).")
        except Exception as e:
            self.log_message(f"Error advancing to Smoothify tab: {e}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {e}")
            except Exception:
                pass

    def show_help(self):
        help_text = (

            "Urban Change Aid - User Guide\n\n"
            "This plugin assists in detecting urban changes from two satellite or aerial images taken at different dates. Follow the tabs in sequence for best results.\n\n"
            " FAQ & Quick Tips \n"
            "- Georeferencing Error: If an image is not georeferenced, use the `Georeference` button to open QGIS's native tool. After saving, the plugin will automatically detect the new file.\n"
            "- Unexpected Results: Detection quality depends heavily on alignment, contrast and binarization threshold. Use the `Preview` buttons and adjust parameters at each stage.\n"
            "- Plugin Slow: Processing large images can be time-consuming. Consider cropping (`Crop`) an area of interest to run quick tests.\n"
            "- What is Sieve?: The `Sieve` filter removes small polygons (noise) from the result, keeping only the most significant change areas. It is highly recommended to apply it to gain/loss masks.\n\n"
            " Step-by-step Guide by Tab \n\n"
            "1. Input Images:\n"
            "   - Select Images: Use the `Browse` buttons or choose layers already loaded in the project for Year 1 (older) and Year 2 (more recent).\n"
            "   - Georeference: If necessary, georeference the images. The plugin will monitor and load the result.\n\n"
            "2. Alignment/Crop:\n"
            "   - Align: Images must have the same dimensions and alignment. Use the `Crop` tool to ensure this.\n"
            "   - Suggest Size: Use this button for the plugin to suggest a crop size corresponding to the intersection of both images.\n"
            "   - Apply Crop: Applies the crop. Cropped images will be used in subsequent steps.\n\n"
            "3. Band/Contrast:\n"
            "   - Extract Band: Select a band (e.g., Red, NIR) that best highlights urban areas. Visible-spectrum bands usually work well.\n"
            "   - Normalize Contrast: Adjust contrast so urban features are well highlighted in both images. Use the histogram to set min/max values.\n\n"
            "4. Binarization:\n"
            "   - Binarize: Converts images to black and white, where (ideally) white represents urban areas and black represents the rest. Adjust the `Threshold` to correctly separate classes.\n"
            "   - Sieve: Applies a filter to clean noise in the binarized image before calculating the difference.\n\n"
            "5. Difference Map:\n"
            "   - Calculate Difference: Generates a map that shows where changes occurred between the two binarized images.\n\n"
            "6. Gain/Loss Mask:\n"
            "   - Generate Masks: Creates two separate masks: `Gain` (new urban areas) and `Loss` (areas that stopped being urban).\n"
            "   - Apply Sieve (Gain/Loss): Crucial step. Applies the Sieve filter directly to the gain and loss masks to remove small irrelevant detections. Adjust the `Threshold` to define the minimum change area to keep.\n\n"
            "7. Vectorization:\n"
            "   - Vectorize: Converts the gain and loss masks (with or without sieve) from raster (pixels) to vector (polygons). The plugin will automatically use the sieved masks if they exist.\n\n"
            "8. Metrics Filter:\n"
            "   - Calculate Metrics: Computes geometric metrics (area, perimeter, etc.) for each change polygon.\n"
            "   - Filter: Use the sliders to filter polygons based on these metrics, removing undesired shapes (e.g., very thin or very small polygons).\n\n"
            "9. Export & Finish:\n"
            "   - Generate Centroids: Creates a point at the center of each filtered change polygon.\n"
            "   - Generate Heatmaps: Creates heatmaps from centroids to visualize the density of changes.\n"
            "   - Export: Export the final results (filtered vectors, centroids) to formats such as Shapefile or GeoPackage.\n"
        )
        QMessageBox.information(
            self.dialog, "Help - Urban Change Aid", help_text)

    def connect_signals(self):
        if hasattr(self.dialog, 'browseYear1'):
            self.dialog.browseYear1.clicked.connect(self.browse_year1)
        if hasattr(self.dialog, 'browseYear2'):
            self.dialog.browseYear2.clicked.connect(self.browse_year2)
        if hasattr(self.dialog, 'georefYear1'):
            self.dialog.georefYear1.clicked.connect(self.georeference_year1)
        if hasattr(self.dialog, 'georefYear2'):
            self.dialog.georefYear2.clicked.connect(self.georeference_year2)
        if hasattr(self.dialog, 'nextToAlignment'):
            self.dialog.nextToAlignment.clicked.connect(self.next_to_alignment)
        if hasattr(self.dialog, 'btnRefreshLayers'):
            self.dialog.btnRefreshLayers.clicked.connect(
                self.populate_project_layers)

        if hasattr(self.dialog, 'checkImageDimensions'):
            self.dialog.checkImageDimensions.clicked.connect(
                self.check_image_dimensions)
        if hasattr(self.dialog, 'btnSuggestSize'):
            self.dialog.btnSuggestSize.clicked.connect(self.suggest_crop_size)
        if hasattr(self.dialog, 'btnApplyCrop'):
            self.dialog.btnApplyCrop.clicked.connect(self.apply_crop)
        if hasattr(self.dialog, 'nextToBand'):
            self.dialog.nextToBand.clicked.connect(self.next_to_band)
        if hasattr(self.dialog, 'chkMaintainResolution'):
            self.dialog.chkMaintainResolution.stateChanged.connect(
                self.toggle_crop_options)

        if hasattr(self.dialog, 'extractBand'):
            self.dialog.extractBand.clicked.connect(self.extract_band)
        if hasattr(self.dialog, 'normalizeContrast'):
            self.dialog.normalizeContrast.clicked.connect(self.open_histogram)
        if hasattr(self.dialog, 'extractNormalizeReset'):
            self.dialog.extractNormalizeReset.clicked.connect(
                self.extract_and_normalize_with_reset)
        if hasattr(self.dialog, 'nextToBinarization'):
            self.dialog.nextToBinarization.clicked.connect(
                self.next_to_binarization)

        if hasattr(self.dialog, 'binarizeButton'):
            self.dialog.binarizeButton.clicked.connect(self.binarize)

        if hasattr(self.dialog, 'nextToSieve'):
            self.dialog.nextToSieve.clicked.connect(self.next_to_sieve)

        if hasattr(self.dialog, 'chkApplySieve'):
            self.dialog.chkApplySieve.stateChanged.connect(
                self.toggle_sieve_options)
        if hasattr(self.dialog, 'applySieveButton'):
            self.dialog.applySieveButton.clicked.connect(self.apply_sieve)

        if hasattr(self.dialog, 'next_to_diff'):
            self.dialog.next_to_diff.clicked.connect(self.next_to_diff)
            QgsMessageLog.logMessage(
                "Connected next_to_diff to next_to_diff", 'UrbanChangeAid', Qgis.Info)

        if hasattr(self.dialog, 'calculateDifference'):
            self.dialog.calculateDifference.clicked.connect(
                self.calculate_difference)
            QgsMessageLog.logMessage(
                "Connected calculateDifference to calculate_difference", 'UrbanChangeAid', Qgis.Info)

        if hasattr(self.dialog, 'next_to_gain_loss'):
            self.dialog.next_to_gain_loss.clicked.connect(
                self.next_to_gain_loss)
        if hasattr(self.dialog, 'generateMasks'):
            self.log_message(
                f"bin_year1_path: {self.bin_year1_path}, exists: {os.path.exists(self.bin_year1_path) if self.bin_year1_path else False}")
            self.log_message(
                f"difference_path: {self.difference_path}, exists: {os.path.exists(self.difference_path) if self.difference_path else False}")
            self.dialog.generateMasks.clicked.connect(
                self.on_generate_gain_loss_clicked)

        # Botão Apply Sieve para Gain/Loss masks
        if hasattr(self.dialog, 'btnApplySieveGainLoss'):
            self.dialog.btnApplySieveGainLoss.clicked.connect(
                lambda: self.apply_sieve_to_masks(
                    threshold=self.dialog.spinSieveThresholdGainLoss.value() if hasattr(
                        self.dialog, 'spinSieveThresholdGainLoss') else 8,
                    connectivity=8
                )
            )
            self.log_message(
                "Connected btnApplySieveGainLoss to apply_sieve_to_masks")

        if hasattr(self.dialog, 'nextToVector'):
            self.dialog.nextToVector.clicked.connect(self.nextToVector)

        if hasattr(self.dialog, 'vectorization_export'):
            self.dialog.vectorization_export.clicked.connect(
                self.vectorize_and_orthogonalize)
        # Removido a pedido do usuário: Botão Preview Vector

        if hasattr(self.dialog, 'btnReprojectUTM'):
            self.dialog.btnReprojectUTM.clicked.connect(
                self.reproject_gain_loss_to_utm)

        if hasattr(self.dialog, 'next_to_metrics'):
            self.dialog.next_to_metrics.clicked.connect(self.next_to_metrics)

        if hasattr(self.dialog, 'previewFilteredButton'):
            self.dialog.previewFilteredButton.clicked.connect(
                self.open_filtered_preview)

        if hasattr(self.dialog, 'calculateMetricsAndFilter'):
            self.dialog.calculateMetricsAndFilter.clicked.connect(
                self.calculate_and_display_metrics)
        else:
            self.log_message(
                "Warning: calculateMetricsAndFilter not found in UI. Please check main.ui.")

        if hasattr(self.dialog, 'previewFilteredButton'):
            self.dialog.previewFilteredButton.clicked.connect(
                self.open_filtered_preview)
        elif hasattr(self.dialog, 'buttonPreviewFilteredVectors'):
            self.dialog.buttonPreviewFilteredVectors.clicked.connect(
                self.open_filtered_preview)
        else:
            self.log_message(
                "⚠️ No 'Preview' button found in UI — check the objectName in main.ui")

        # Conexões existentes pros sliders (você já tem isso, só pra contexto)
        if hasattr(self.dialog, 'sliderArea'):
            self.dialog.sliderArea.valueChanged.connect(
                self.filter_vectors_by_metrics)
        if hasattr(self.dialog, 'sliderPerimeter'):
            self.dialog.sliderPerimeter.valueChanged.connect(
                self.filter_vectors_by_metrics)
        if hasattr(self.dialog, 'sliderElongation'):
            self.dialog.sliderElongation.valueChanged.connect(
                self.filter_vectors_by_metrics)
        if hasattr(self.dialog, 'sliderRectangularity'):
            self.dialog.sliderRectangularity.valueChanged.connect(
                self.filter_vectors_by_metrics)

        # Agora, adiciona o sync bidirecional: slider atualiza spin, e spin atualiza slider + roda filtro
        # Pra área (repita o padrão pros outros)
        if hasattr(self.dialog, 'sliderArea') and hasattr(self.dialog, 'spinArea'):
            # Slider muda → spin copia o valor
            self.dialog.sliderArea.valueChanged.connect(
                lambda val: self.dialog.spinArea.setValue(val))
            # Spin muda → slider copia + roda filtro
            self.dialog.spinArea.valueChanged.connect(
                lambda val: [self.dialog.sliderArea.setValue(val), self.filter_vectors_by_metrics()])

        # Perímetro (mesmo padrão)
        if hasattr(self.dialog, 'sliderPerimeter') and hasattr(self.dialog, 'spinPerimeter'):
            self.dialog.sliderPerimeter.valueChanged.connect(
                lambda val: self.dialog.spinPerimeter.setValue(val))
            self.dialog.spinPerimeter.valueChanged.connect(lambda val: [
                                                           self.dialog.sliderPerimeter.setValue(val), self.filter_vectors_by_metrics()])

        # Elongação (divida por 10 se o slider for em escala 0-1000, ex: val / 10.0)
        if hasattr(self.dialog, 'sliderElongation') and hasattr(self.dialog, 'spinElongation'):
            self.dialog.sliderElongation.valueChanged.connect(
                # Ajuste a escala se preciso
                lambda val: self.dialog.spinElongation.setValue(val / 10.0))
            self.dialog.spinElongation.valueChanged.connect(lambda val: [
                                                            self.dialog.sliderElongation.setValue(int(val * 10)), self.filter_vectors_by_metrics()])

        # Retangularidade (divida por 100 se slider 0-100)
        if hasattr(self.dialog, 'sliderRectangularity') and hasattr(self.dialog, 'spinRectangularity'):
            self.dialog.sliderRectangularity.valueChanged.connect(
                lambda val: self.dialog.spinRectangularity.setValue(val / 100.0))
            self.dialog.spinRectangularity.valueChanged.connect(lambda val: [
                                                                self.dialog.sliderRectangularity.setValue(int(val * 100)), self.filter_vectors_by_metrics()])
        # No connect_signals(), após as conexões dos sliders e spins:
        if hasattr(self.dialog, 'btnApplyFilter'):
            self.dialog.btnApplyFilter.clicked.connect(
                self.apply_filter_and_show_table)

        if hasattr(self.dialog, 'btnExportSelection'):
            self.dialog.btnExportSelection.clicked.connect(
                self.export_filtered_vectors)

        if hasattr(self.dialog, 'nextToSmoothify'):
            self.dialog.nextToSmoothify.clicked.connect(self.next_to_smoothify)

        # Connect orthogonalize/simplify helper button if present (correct objectName)
        if hasattr(self.dialog, 'orthogonalize_or_simplifyButton'):
            # Connect to handler that opens helper dialog for simplifying/orthogonalizing
            # the gain/loss filtered shapefiles located in `self.temp_dir`.
            # Use a clear handler name and ensure the button is visible.
            self.dialog.orthogonalize_or_simplifyButton.clicked.connect(
                self.on_orthogonalize_or_simplify_button_clicked)
            try:
                self.dialog.orthogonalize_or_simplifyButton.show()
            except Exception:
                pass

        # Rename navigation button to 'nextToExport' if present; keep backward compatibility
        if hasattr(self.dialog, 'nextToExport'):
            self.dialog.nextToExport.clicked.connect(self.next_to_export)
        elif hasattr(self.dialog, 'nextToCentroids'):
            # backward-compat: connect old name to new handler
            self.dialog.nextToCentroids.clicked.connect(self.next_to_export)

        if hasattr(self.dialog, 'generate_centroids'):
            self.dialog.generate_centroids.clicked.connect(
                self.generate_centroids)

        # Conexão do botão de Heatmap (Problema 1) - Conexão única e correta.
        # O nome do objeto no .ui deve ser 'generate_heatmaps_btn' ou 'generate_heatmaps'.
        # Tentamos o nome mais provável que causou a duplicação se não for encontrado.
        heatmap_btn = self.dialog.findChild(QPushButton, "generate_heatmaps_btn")
        if not heatmap_btn:
            heatmap_btn = self.dialog.findChild(QPushButton, "generate_heatmaps")

        if heatmap_btn:
            try:
                heatmap_btn.clicked.connect(self.generate_heatmaps)
                self.log_message(f"Connected 'Generate Heatmaps' button ({heatmap_btn.objectName()}).")
            except Exception as e:
                self.log_message(f"Warning: failed to connect heatmap button ({heatmap_btn.objectName()}): {e}")
        else:
            self.log_message("Warning: 'Generate Heatmaps' button not found in UI for connection.")
        # Código de conexão antigo para 'export_all' removido. A nova conexão
        # para 'export_all_results_btn' foi adicionada na seção de conexões.ise — keep the plugin usable.

        if hasattr(self.dialog, 'resetButton'):
            self.dialog.resetButton.clicked.connect(self.reset_plugin_state)

    def on_orthogonalize_or_simplify_button_clicked(self):
        """Open a helper dialog to simplify/orthogonalize gain/loss shapefiles in temp_dir.

        - Defaults to `gain_filtered.shp` and `loss_filtered.shp` inside `self.temp_dir`.
        - Preview loads a temporary layer into the project (tracked so it can be removed).
        - Apply & Load writes output shapefile into `self.temp_dir` and adds it to the project.
        - Next button enables and moves to the next tab (non-mandatory).
        """
        try:
            from qgis import processing
        except Exception:
            processing = None

        gain_path = os.path.join(self.temp_dir, "gain_filtered.shp")
        loss_path = os.path.join(self.temp_dir, "loss_filtered.shp")

        available = []
        if os.path.exists(gain_path):
            available.append(("Gain", gain_path))
        if os.path.exists(loss_path):
            available.append(("Loss", loss_path))

        if not available:
            QMessageBox.warning(self.dialog, "Not Found",
                                "No filtered shapefiles found in temp directory:\n"
                                f"{gain_path}\n{loss_path}\n\nRun vectorization first or check the temp folder.")
            return

        dlg = QDialog(self.dialog)
        dlg.setWindowTitle("Simplify / Orthogonalize - Preview & Apply")
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Input Layer:"))
        combo = QComboBox()
        for label, path in available:
            combo.addItem(label, path)
        layout.addWidget(combo)

        # Options
        opts_layout = QHBoxLayout()
        chk_simplify = QCheckBox("Simplify")
        chk_simplify.setChecked(True)
        opts_layout.addWidget(chk_simplify)
        chk_orth = QCheckBox("Orthogonalize (if available)")
        chk_orth.setChecked(False)
        opts_layout.addWidget(chk_orth)
        layout.addLayout(opts_layout)

        tol_layout = QHBoxLayout()
        tol_layout.addWidget(QLabel("Simplify tolerance (map units):"))
        tol_spin = QDoubleSpinBox()
        tol_spin.setRange(0.0, 1e6)
        tol_spin.setDecimals(3)
        tol_spin.setValue(1.0)
        tol_layout.addWidget(tol_spin)
        layout.addLayout(tol_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        preview_btn = QPushButton("Preview")
        apply_btn = QPushButton("Apply & Load")
        next_btn = QPushButton("Next")
        close_btn = QPushButton("Close")
        btn_layout.addWidget(preview_btn)
        btn_layout.addWidget(apply_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(next_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Track preview layers so we can remove/replace them
        if not hasattr(self, '_simplify_preview_layers'):
            self._simplify_preview_layers = {}

        def _remove_preview(label):
            lid = self._simplify_preview_layers.get(label)
            if lid:
                try:
                    QgsProject.instance().removeMapLayer(lid)
                except Exception:
                    pass
                self._simplify_preview_layers.pop(label, None)

        def run_processing_for(label, in_path, out_path):
            # Sequence: simplify -> orthogonalize (if requested and available)
            tmp_path = out_path
            try:
                current_in = in_path
                # Simplify
                if chk_simplify.isChecked():
                    params = {
                        'INPUT': current_in,
                        'METHOD': 0,  # distance
                        'TOLERANCE': float(tol_spin.value()),
                        'OUTPUT': tmp_path
                    }
                    if processing:
                        processing.run("native:simplifygeometries", params)
                    else:
                        raise RuntimeError(
                            "Processing framework not available")
                    current_in = tmp_path

                # Orthogonalize (best-effort)
                if chk_orth.isChecked():
                    ort_path = os.path.splitext(tmp_path)[0] + "_ort.shp"
                    try:
                        if processing:
                            processing.run("qgis:orthogonalize", {
                                           'INPUT': current_in, 'OUTPUT': ort_path})
                            current_in = ort_path
                        else:
                            raise RuntimeError(
                                "Processing framework not available")
                    except Exception:
                        # If orthogonalize not available, warn and continue with current_in
                        QMessageBox.warning(dlg, "Orthogonalize Unavailable",
                                            "Orthogonalize algorithm not available on this QGIS installation.\n"
                                            "Only simplification will be applied.")

                return current_in
            except Exception as e:
                QMessageBox.warning(dlg, "Processing Error",
                                    f"Error running processing: {e}")
                return None

        def do_preview():
            label = combo.currentText()
            in_path = combo.currentData()
            out_tmp = os.path.join(
                self.temp_dir, f"preview_{label.lower()}.shp")
            # remove existing preview for label
            _remove_preview(label)
            result_path = run_processing_for(label, in_path, out_tmp)
            if not result_path:
                return
            # load preview layer
            v = QgsVectorLayer(result_path, f"{label} Preview", "ogr")
            if not v.isValid():
                QMessageBox.warning(dlg, "Preview Error",
                                    "Failed to load preview layer.")
                return
            QgsProject.instance().addMapLayer(v)
            self._simplify_preview_layers[label] = v.id()
            QMessageBox.information(
                dlg, "Preview Loaded", f"Preview layer loaded: {v.name()}\n\nIt will be removed when a new preview is created or the plugin is reset.")

        def do_apply():
            label = combo.currentText()
            in_path = combo.currentData()
            out_name = f"{label.lower()}_processed.shp"
            out_path = os.path.join(self.temp_dir, out_name)
            # Run processing and save output to out_path
            res = run_processing_for(label, in_path, out_path)
            if not res:
                return
            # If processing wrote to a different path (e.g., orthogonalize), copy/move to desired out_path
            if res != out_path:
                try:
                    # overwrite if exists
                    if os.path.exists(out_path):
                        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
                            try:
                                os.remove(os.path.splitext(out_path)[0] + ext)
                            except Exception:
                                pass
                    # Copy all related shapefile files
                    res_base_name = os.path.splitext(os.path.basename(res))[0]
                    res_dir = os.path.dirname(res)
                    for filename in os.listdir(res_dir):
                        if filename.startswith(res_base_name):
                            shutil.copy(os.path.join(res_dir, filename), os.path.join(
                                os.path.dirname(out_path), filename.replace(res_base_name, os.path.splitext(os.path.basename(out_path))[0])))
                except Exception as e:
                    self.log_message(
                        f"Error copying shapefile components: {e}")
                    pass

            # Remove previous preview for this label
            _remove_preview(label)

            # Load output into project and notify
            layer = QgsVectorLayer(out_path, f"{label} Processed", "ogr")
            if not layer.isValid():
                QMessageBox.warning(
                    dlg, "Load Error", "Failed to load processed layer into project.")
                return
            QgsProject.instance().addMapLayer(layer)
            self.log_message(f"✅ Processed layer added: {layer.name()}")
            QMessageBox.information(dlg, "Success", f"Processed layer added to project: {layer.name()}")

        def do_next():
            # enable next tab and advance one step (non-mandatory)
            tw = getattr(self.dialog, 'tabWidget', None)
            if tw:
                cur = tw.currentIndex()
                if cur + 1 < tw.count():
                    tw.setTabEnabled(cur + 1, True)
                    tw.setCurrentIndex(cur + 1)
            dlg.accept()

        preview_btn.clicked.connect(do_preview)
        apply_btn.clicked.connect(do_apply)
        next_btn.clicked.connect(do_next)
        close_btn.clicked.connect(dlg.reject)

        dlg.exec_()

    def log_message(self, message):
        if hasattr(self, 'log_text'):
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)
            self.log_text.append(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")
            QApplication.processEvents()

    def _is_path_loaded(self, path):
        """Return True if any project layer is using the given file path as source."""
        try:
            for layer in QgsProject.instance().mapLayers().values():
                try:
                    if hasattr(layer, 'source') and layer.source() == path:
                        return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    def _safe_remove(self, path):
        """Remove a temporary file if no layer is using it."""
        try:
            if not path or not os.path.exists(path):
                return False
            if self._is_path_loaded(path):
                QgsMessageLog.logMessage(
                    f"Skipping removal of {path}: layer still loaded.", 'UrbanChangeAid', Qgis.Info)
                return False
            os.remove(path)
            QgsMessageLog.logMessage(
                f"Removed temporary file {path}.", 'UrbanChangeAid', Qgis.Info)
            return True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to remove temp file {path}: {e}", 'UrbanChangeAid', Qgis.Warning)
            return False

    def toggle_crop_options(self, state):
        self.dialog.spinCropWidth.setEnabled(not state)
        self.dialog.spinCropHeight.setEnabled(not state)
        if state:
            self.dialog.labelCropInfo.setText(
                "Crop will maintain original pixel resolution.")
        else:
            self.dialog.labelCropInfo.setText(
                "Specify pixel dimensions; may cause resampling.")

    def toggle_sieve_options(self, state):
        if hasattr(self.dialog, 'spinSieveThreshold'):
            self.dialog.spinSieveThreshold.setEnabled(state == Qt.Checked)
        if hasattr(self.dialog, 'applySieveButton'):
            self.dialog.applySieveButton.setEnabled(state == Qt.Checked)
        self.log_message(
            f"Sieve option toggled: {'ON' if state == Qt.Checked else 'OFF'}")

    def populate_project_layers(self):
        self.dialog.comboYear1.clear()
        self.dialog.comboYear2.clear()
        self.dialog.comboYear1.addItem("Select from project or browse new...")
        self.dialog.comboYear2.addItem("Select from project or browse new...")
        layers = [layer for layer in QgsProject.instance(
        ).mapLayers().values() if isinstance(layer, QgsRasterLayer)]
        for layer in layers:
            self.dialog.comboYear1.addItem(layer.name(), layer.source())
            self.dialog.comboYear2.addItem(layer.name(), layer.source())

    def start_layer_monitoring(self, year):
        """Start monitoring for new layers added to the project after georeferencing."""
        self.monitoring_year = year
        self.layer_count_before = len(QgsProject.instance().mapLayers())

        # Connect to layer added signal
        QgsProject.instance().layersAdded.connect(self.on_layers_added)
        self.log_message(
            f"Started monitoring for new georeferenced layers ({year})")

    def on_layers_added(self, layers):
        """Called when new layers are added to the project."""
        if not self.monitoring_year:
            return

        # Check if any new raster layer was added
        for layer in layers:
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                # Check if it's georeferenced
                if self.check_georeferencing(layer.source()):
                    self.log_message(
                        f"New georeferenced layer detected: {layer.name()}")

                    # Update the appropriate year path
                    if self.monitoring_year == 'year1':
                        self.year1_path = layer.source()
                        self.dialog.comboYear1.setCurrentText(layer.name())
                        QMessageBox.information(
                            self.dialog,
                            "Georeferenced File Detected",
                            f"The georeferenced file '{layer.name()}' has been detected and set as Year 1 image.\n\n"
                            "You can now proceed to the next step."
                        )
                    elif self.monitoring_year == 'year2':
                        self.year2_path = layer.source()
                        self.dialog.comboYear2.setCurrentText(layer.name())
                        QMessageBox.information(
                            self.dialog,
                            "Georeferenced File Detected",
                            f"The georeferenced file '{layer.name()}' has been detected and set as Year 2 image.\n\n"
                            "You can now proceed to the next step."
                        )

                    # Refresh layer list
                    self.populate_project_layers()

                    # Stop monitoring
                    self.stop_layer_monitoring()
                    break

    def stop_layer_monitoring(self):
        """Stop monitoring for new layers."""
        try:
            QgsProject.instance().layersAdded.disconnect(self.on_layers_added)
        except:
            pass
        self.monitoring_year = None
        self.log_message("Stopped layer monitoring")

    def check_georeferencing(self, file_path):
        """Check if a raster file is georeferenced."""
        try:
            ds = gdal.Open(file_path)
            if ds is None:
                return False

            # Check if has valid projection
            projection = ds.GetProjection()
            geotransform = ds.GetGeoTransform()
            ds = None

            # Default geotransform is (0, 1, 0, 0, 0, 1) - not georeferenced
            has_projection = projection is not None and projection != ""
            has_geotransform = geotransform is not None and geotransform != (
                0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

            return has_projection and has_geotransform
        except Exception as e:
            self.log_message(f"Error checking georeferencing: {str(e)}")
            return False

    def browse_year1(self):
        file_path, _ = QFileDialog.getOpenFileName(self.dialog, "Select Year 1 Image", "",
                                                   "Image Files (*.tif *.tiff *.jpg *.jpeg *.png)")
        if file_path:
            self.year1_path = file_path
            self.dialog.comboYear1.setCurrentText(os.path.basename(file_path))

            # Check if georeferenced
            if not self.check_georeferencing(file_path):
                QMessageBox.warning(
                    self.dialog,
                    "Image Not Georeferenced",
                    f"The selected image '{os.path.basename(file_path)}' is not georeferenced.\n\n"
                    "Please click the 'Georeference Year 1' button to open the QGIS Georeferencer tool.\n\n"
                    "After georeferencing, the plugin will automatically detect the new georeferenced file."
                )
                self.log_message(
                    f"Year 1 image not georeferenced: {file_path}")
            else:
                self.log_message(f"Year 1 image is georeferenced: {file_path}")

    def browse_year2(self):
        file_path, _ = QFileDialog.getOpenFileName(self.dialog, "Select Year 2 Image", "",
                                                   "Image Files (*.tif *.tiff *.jpg *.jpeg *.png)")
        if file_path:
            self.year2_path = file_path
            self.dialog.comboYear2.setCurrentText(os.path.basename(file_path))

            # Check if georeferenced
            if not self.check_georeferencing(file_path):
                QMessageBox.warning(
                    self.dialog,
                    "Image Not Georeferenced",
                    f"The selected image '{os.path.basename(file_path)}' is not georeferenced.\n\n"
                    "Please click the 'Georeference Year 2' button to open the QGIS Georeferencer tool.\n\n"
                    "After georeferencing, the plugin will automatically detect the new georeferenced file."
                )
                self.log_message(
                    f"Year 2 image not georeferenced: {file_path}")
            else:
                self.log_message(f"Year 2 image is georeferenced: {file_path}")

    def georeference_year1(self):
        """Opens the QGIS Georeferencer tool and monitors for new georeferenced files."""
        if self.year1_path:
            try:
                # Open QGIS native georeferencer
                self.iface.showGeoreferencer()
                self.log_message(
                    f"Georeferencer opened for: {self.year1_path}")

                # Show info message
                QMessageBox.information(
                    self.dialog,
                    "Georeferencer Opened",
                    f"The QGIS Georeferencer has been opened.\n\n"
                    f"Please georeference the image: {os.path.basename(self.year1_path)}\n\n"
                    "After saving the georeferenced file, the plugin will automatically detect it in the project layers."
                )

                # Start monitoring for new layers
                self.start_layer_monitoring('year1')

            except AttributeError:
                # Fallback if showGeoreferencer is not available
                QMessageBox.warning(
                    self.dialog,
                    "Georeferencer Not Available",
                    "The Georeferencer tool is not available in this QGIS version.\n\n"
                    "Please open it manually from: Raster → Georeferencer\n\n"
                    f"Selected file: {os.path.basename(self.year1_path)}"
                )
            except Exception as e:
                self.log_message(f"Error opening georeferencer: {str(e)}")
                QMessageBox.warning(
                    self.dialog,
                    "Error",
                    f"Could not open the georeferencer automatically.\n"
                    f"Please open manually from: Raster → Georeferencer\n\n"
                    f"Error: {str(e)}"
                )
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please select Year 1 image first.")

    def georeference_year2(self):
        """Opens the QGIS Georeferencer tool and monitors for new georeferenced files."""
        if self.year2_path:
            try:
                # Open QGIS native georeferencer
                self.iface.showGeoreferencer()
                self.log_message(
                    f"Georeferencer opened for: {self.year2_path}")

                # Show info message
                QMessageBox.information(
                    self.dialog,
                    "Georeferencer Opened",
                    f"The QGIS Georeferencer has been opened.\n\n"
                    f"Please georeference the image: {os.path.basename(self.year2_path)}\n\n"
                    "After saving the georeferenced file, the plugin will automatically detect it in the project layers."
                )

                # Start monitoring for new layers
                self.start_layer_monitoring('year2')

            except AttributeError:
                # Fallback if showGeoreferencer is not available
                QMessageBox.warning(
                    self.dialog,
                    "Georeferencer Not Available",
                    "The Georeferencer tool is not available in this QGIS version.\n\n"
                    "Please open it manually from: Raster → Georeferencer\n\n"
                    f"Selected file: {os.path.basename(self.year2_path)}"
                )
            except Exception as e:
                self.log_message(f"Error opening georeferencer: {str(e)}")
                QMessageBox.warning(
                    self.dialog,
                    "Error",
                    f"Could not open the georeferencer automatically.\n"
                    f"Please open manually from: Raster → Georeferencer\n\n"
                    f"Error: {str(e)}"
                )
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please select Year 2 image first.")

    def next_to_alignment(self):
        if not self.year1_path and self.dialog.comboYear1.currentIndex() > 0:
            self.year1_path = self.dialog.comboYear1.currentData()
        if not self.year2_path and self.dialog.comboYear2.currentIndex() > 0:
            self.year2_path = self.dialog.comboYear2.currentData()

        if self.year1_path and self.year2_path:
            if self.year1_path == self.year2_path:
                QMessageBox.warning(
                    self.dialog, "Warning", "Year 1 and Year 2 are the same image. Results will be duplicated and difference will be zero.")
                return
            self.dialog.tabWidget.setTabEnabled(1, True)
            self.dialog.tabWidget.setCurrentIndex(1)
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please select both Year 1 and Year 2 images.")

    def check_image_dimensions(self):
        if not self.year1_path or not self.year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please select both images first.")
            return

        try:
            ds1 = gdal.Open(self.year1_path)
            ds2 = gdal.Open(self.year2_path)

            if ds1 is None or ds2 is None:
                QMessageBox.warning(self.dialog, "Error",
                                    "Could not open one or both images.")
                return

            width1, height1 = ds1.RasterXSize, ds1.RasterYSize
            width2, height2 = ds2.RasterXSize, ds2.RasterYSize

            gt1 = ds1.GetGeoTransform()
            gt2 = ds2.GetGeoTransform()

            proj1 = ds1.GetProjection()
            proj2 = ds2.GetProjection()

            info_text = f"Year 1: {width1} x {height1} pixels\n"
            info_text += f"Year 2: {width2} x {height2} pixels\n\n"

            spatial_aligned = (gt1 == gt2 and proj1 == proj2)
            if width1 == width2 and height1 == height2 and spatial_aligned:
                info_text += "✓ Images are perfectly aligned"
            else:
                info_text += "⚠ Images require alignment and cropping"

            self.dialog.labelImageInfo.setText(info_text)

            ds1 = None
            ds2 = None

        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error checking dimensions: {str(e)}")

    def suggest_crop_size(self):
        if not self.year1_path or not self.year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please select both images first.")
            return

        try:
            overlap_info = self._calculate_overlap_area()
            ds1 = gdal.Open(self.year1_path)
            width1, height1 = ds1.RasterXSize, ds1.RasterYSize
            ds1 = None

            if overlap_info and overlap_info['width'] > 0 and overlap_info['height'] > 0:
                suggested_width = max(100, int(overlap_info['width'] * 0.9))
                suggested_height = max(100, int(overlap_info['height'] * 0.9))
            else:
                suggested_width = max(100, int(min(width1, height1) * 0.8))
                suggested_height = suggested_width

            self.dialog.spinCropWidth.setValue(suggested_width)
            self.dialog.spinCropHeight.setValue(suggested_height)

            QMessageBox.information(self.dialog, "Suggestion",
                                    f"Suggested: {suggested_width}x{suggested_height} pixels based on data.")

        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error suggesting size: {str(e)}")

    def _calculate_overlap_area(self):
        try:
            ds1 = gdal.Open(self.year1_path)
            ds2 = gdal.Open(self.year2_path)

            if ds1 is None or ds2 is None:
                return None

            gt1 = ds1.GetGeoTransform()
            bounds1 = self._get_image_bounds(ds1)
            bounds2 = self._get_image_bounds(ds2)

            left = max(bounds1["left"], bounds2["left"])
            right = min(bounds1["right"], bounds2["right"])
            top = min(bounds1["top"], bounds2["top"])
            bottom = max(bounds1["bottom"], bounds2["bottom"])

            if left < right and bottom < top:
                pixel_width = abs(gt1[1])
                pixel_height = abs(gt1[5])

                overlap_width = int((right - left) / pixel_width)
                overlap_height = int((top - bottom) / pixel_height)

                ds1 = None
                ds2 = None

                return {
                    "width": overlap_width,
                    "height": overlap_height,
                    "left": left,
                    "right": right,
                    "top": top,
                    "bottom": bottom
                }

            ds1 = None
            ds2 = None
            return None

        except Exception as e:
            print(f"Error calculating overlap: {e}")
            return None

    def _get_image_bounds(self, dataset):
        gt = dataset.GetGeoTransform()
        width = dataset.RasterXSize
        height = dataset.RasterYSize

        left = gt[0]
        top = gt[3]
        right = left + width * gt[1]
        bottom = top + height * gt[5]

        return {
            "left": left,
            "right": right,
            "top": top,
            "bottom": bottom
        }

    def apply_crop(self):
        if not self.year1_path or not self.year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please select both images first.")
            return

        try:
            maintain_res = hasattr(
                self.dialog, 'chkMaintainResolution') and self.dialog.chkMaintainResolution.isChecked()
            crop_width = self.dialog.spinCropWidth.value() if not maintain_res else None
            crop_height = self.dialog.spinCropHeight.value() if not maintain_res else None

            if hasattr(self, 'selected_crop_bounds') and self.selected_crop_bounds:
                bounds = {
                    'left': self.selected_crop_bounds.xMinimum(), 'right': self.selected_crop_bounds.xMaximum(),
                    'top': self.selected_crop_bounds.yMaximum(), 'bottom': self.selected_crop_bounds.yMinimum()
                }
            elif self.dialog.radioCentroidCrop.isChecked():
                bounds = self._get_centroid_bounds(crop_width, crop_height)
            else:
                bounds = self._calculate_overlap_area()

            if not bounds:
                QMessageBox.warning(self.dialog, "Warning",
                                    "No overlapping area found.")
                return

            if maintain_res:
                self._crop_without_resampling(bounds)
            else:
                self._crop_with_resampling(bounds, crop_width, crop_height)

            if self.aligned_year1_path and self.aligned_year2_path:
                self._load_to_project(
                    self.aligned_year1_path, "Aligned Year 1")
                self._load_to_project(
                    self.aligned_year2_path, "Aligned Year 2")
                QMessageBox.information(
                    self.dialog, "Success", "Images cropped and aligned successfully.")
                self.dialog.tabWidget.setTabEnabled(2, True)
                self.dialog.tabWidget.setCurrentIndex(2)

        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error applying crop: {str(e)}")

    def _get_centroid_bounds(self, crop_width, crop_height):
        overlap_info = self._calculate_overlap_area()
        if not overlap_info:
            raise ValueError("No overlap for centroid crop.")
        center_x = (overlap_info["left"] + overlap_info["right"]) / 2
        center_y = (overlap_info["top"] + overlap_info["bottom"]) / 2
        ds1 = gdal.Open(self.year1_path)
        gt1 = ds1.GetGeoTransform()
        pixel_width_geo, pixel_height_geo = abs(gt1[1]), abs(gt1[5])
        ds1 = None
        half_width = (crop_width / 2) * pixel_width_geo if crop_width else (overlap_info['right'] - overlap_info[
            'left']) / 2
        half_height = (crop_height / 2) * pixel_height_geo if crop_height else (overlap_info['top'] - overlap_info[
            'bottom']) / 2
        return {
            'left': center_x - half_width, 'right': center_x + half_width,
            'top': center_y + half_height, 'bottom': center_y - half_height
        }

    def _crop_without_resampling(self, bounds):
        output_dir = os.path.join(self.temp_dir, "aligned_images")
        os.makedirs(output_dir, exist_ok=True)
        self.aligned_year1_path = os.path.join(output_dir, "aligned_year1.tif")
        self.aligned_year2_path = os.path.join(output_dir, "aligned_year2.tif")
        gdal.Translate(self.aligned_year1_path, self.year1_path,
                       projWin=[bounds['left'], bounds['top'], bounds['right'], bounds['bottom']])
        gdal.Translate(self.aligned_year2_path, self.year2_path,
                       projWin=[bounds['left'], bounds['top'], bounds['right'], bounds['bottom']])

    def _crop_with_resampling(self, bounds, crop_width, crop_height):
        output_dir = os.path.join(self.temp_dir, "aligned_images")
        os.makedirs(output_dir, exist_ok=True)
        self.aligned_year1_path = os.path.join(output_dir, "aligned_year1.tif")
        self.aligned_year2_path = os.path.join(output_dir, "aligned_year2.tif")
        warp_options = gdal.WarpOptions(
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            width=crop_width, height=crop_height, resampleAlg=gdal.GRA_NearestNeighbour,
            srcNodata=0, dstNodata=0, format="GTiff"
        )
        gdal.Warp(self.aligned_year1_path,
                  self.year1_path, options=warp_options)
        gdal.Warp(self.aligned_year2_path,
                  self.year2_path, options=warp_options)

    def _load_to_project(self, path, name):
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            QMessageBox.warning(self.dialog, "Error",
                                f"Failed to load layer: {name}")
            return

        unique_suffix = datetime.now().strftime("%H%M%S")
        unique_name = f"{name} [{unique_suffix}]" if SAFE_NO_REMOVE_LAYERS else name
        if unique_name != name:
            layer.setName(unique_name)

        if not SAFE_NO_REMOVE_LAYERS:
            existing_layers = QgsProject.instance().mapLayersByName(name)
            for ex_layer in existing_layers:
                if ex_layer.id() == getattr(self, "selected_layer", None):
                    self.selected_layer = None
                if ex_layer.id() == getattr(self, "visualization_layer", None):
                    self.visualization_layer = None
                QgsProject.instance().removeMapLayer(ex_layer.id())
                if ex_layer.id() in self.loaded_layer_ids:
                    self.loaded_layer_ids.remove(ex_layer.id())

        # Adiciona a camada ao projeto
        QgsProject.instance().addMapLayer(layer)

        # Configura o renderer para máscaras binárias (Gain/Loss)
        if "Binarized" in name or "Mask" in name:
            try:
                # Create discrete color ramp: 0 -> transparent (background), 255 -> color
                if "Gain" in name:
                    clr0 = QColor(0, 0, 0, 0)
                    clr1 = QColor(255, 0, 0, 255)
                elif "Loss" in name:
                    clr0 = QColor(0, 0, 0, 0)
                    clr1 = QColor(0, 0, 255, 255)
                else:
                    clr0 = QColor(0, 0, 0, 0)
                    clr1 = QColor(255, 255, 255, 255)

                color_items = [
                    QgsColorRampShader.ColorRampItem(0, clr0, '0'),
                    QgsColorRampShader.ColorRampItem(255, clr1, '255')
                ]
                color_ramp = QgsColorRampShader()
                color_ramp.setColorRampItemList(color_items)
                color_ramp.setColorRampType(QgsColorRampShader.Discrete)

                raster_shader = QgsRasterShader()
                raster_shader.setRasterShaderFunction(color_ramp)

                renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, raster_shader)

                # Force contrast range
                try:
                    ce = renderer.contrastEnhancement()
                    if ce is not None:
                        ce.setMinimumValue(0)
                        ce.setMaximumValue(255)
                except Exception:
                    pass

                layer.setRenderer(renderer)
                layer.triggerRepaint()

                # Try setting raster transparency (fallbacks for different QGIS APIs)
                try:
                    from qgis.core import QgsRasterTransparency
                    try:
                        entry = QgsRasterTransparency.TransparentSingleValuePixel(0, 0)
                        trans = QgsRasterTransparency()
                        trans.setTransparentSingleValuePixelList([entry])
                        renderer.setRasterTransparency(trans)
                        layer.triggerRepaint()
                        self.log_message(f"Applied pseudo-color renderer and transparency for {name}")
                    except Exception:
                        # alternate API
                        trans = QgsRasterTransparency()
                        entry = QgsRasterTransparency.TransparentSingleValuePixel()
                        entry.setValue(0)
                        entry.setOpacity(0)
                        trans.setTransparentSingleValuePixelList([entry])
                        renderer.setRasterTransparency(trans)
                        layer.triggerRepaint()
                        self.log_message(f"Applied transparency fallback for {name}")
                except Exception as e:
                    self.log_message(f"Could not apply raster transparency for {name}: {e}")

            except Exception as e:
                # Fallback: simple gray renderer with contrast enhancement
                try:
                    renderer = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
                    try:
                        ce = renderer.contrastEnhancement()
                        if ce is not None:
                            ce.setMinimumValue(0)
                            ce.setMaximumValue(255)
                    except Exception:
                        pass
                    layer.setRenderer(renderer)
                    layer.triggerRepaint()
                    self.log_message(f"Applied gray fallback renderer for {name}")
                except Exception as e2:
                    self.log_message(f"Failed to set renderer for {name}: {e} / {e2}")
        self.loaded_layer_ids.append(layer.id())

        if "Year 1" in name:
            self.selected_layer = layer.id()
        elif "Year 2" in name:
            self.visualization_layer = layer.id()

        return layer.id()

    def next_to_band(self):
        if self.aligned_year1_path and self.aligned_year2_path:
            self.dialog.tabWidget.setTabEnabled(2, True)
            self.dialog.tabWidget.setCurrentIndex(2)
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please align and crop images first.")

    def extract_band(self):
        if not self.aligned_year1_path or not self.aligned_year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please align and crop the images first.")
            return
        try:
            band_index = int(self.dialog.spinBandIndex.value())
            output_dir = os.path.join(self.temp_dir, "extracted_bands")
            os.makedirs(output_dir, exist_ok=True)
            self.band_year1_path = os.path.join(
                output_dir, f"band_{band_index}_year1.tif")
            self.band_year2_path = os.path.join(
                output_dir, f"band_{band_index}_year2.tif")

            for path in [self.band_year1_path, self.band_year2_path]:
                if os.path.exists(path):
                    self._safe_remove(path)

            ds1 = gdal.Open(self.aligned_year1_path)
            ds2 = gdal.Open(self.aligned_year2_path)
            if ds1 is None or ds2 is None:
                raise Exception("Could not open aligned images.")

            if band_index < 1 or band_index > ds1.RasterCount or band_index > ds2.RasterCount:
                raise Exception(
                    f"Invalid band index {band_index}. Year 1 has {ds1.RasterCount} bands, Year 2 has {ds2.RasterCount} bands.")

            band1 = ds1.GetRasterBand(band_index).ReadAsArray()
            band2 = ds2.GetRasterBand(band_index).ReadAsArray()

            if band1 is None or band2 is None:
                raise Exception("Failed to read band data.")

            band1 = band1.astype(np.float32)
            band2 = band2.astype(np.float32)
            valid1 = band1 != 0
            valid2 = band2 != 0
            band1[~valid1] = np.nan
            band2[~valid2] = np.nan

            if np.all(np.isnan(band1)) or np.all(np.isnan(band2)):
                raise Exception(
                    "No valid data in one or both bands after removing zeros.")

            driver = gdal.GetDriverByName('GTiff')
            out1 = driver.Create(
                self.band_year1_path, ds1.RasterXSize, ds1.RasterYSize, 1, gdal.GDT_Float32)
            if out1 is None:
                raise Exception(
                    f"Failed to create output file: {self.band_year1_path}")
            out1.SetGeoTransform(ds1.GetGeoTransform())
            out1.SetProjection(ds1.GetProjection())
            out1.GetRasterBand(1).WriteArray(band1)
            out1.GetRasterBand(1).SetNoDataValue(np.nan)
            out1.FlushCache()
            out1 = None

            out2 = driver.Create(
                self.band_year2_path, ds2.RasterXSize, ds2.RasterYSize, 1, gdal.GDT_Float32)
            if out2 is None:
                raise Exception(
                    f"Failed to create output file: {self.band_year2_path}")
            out2.SetGeoTransform(ds2.GetGeoTransform())
            out2.SetProjection(ds2.GetProjection())
            out2.GetRasterBand(1).WriteArray(band2)
            out2.GetRasterBand(1).SetNoDataValue(np.nan)
            out2.FlushCache()
            out2 = None

            ds1 = None
            ds2 = None

            if not os.path.exists(self.band_year1_path) or not os.path.exists(self.band_year2_path):
                raise Exception(
                    "Failed to create one or both band output files.")

            self._load_to_project(self.band_year1_path,
                                  f"Band {band_index} - Year 1")
            self._load_to_project(self.band_year2_path,
                                  f"Band {band_index} - Year 2")
            self.log_message(
                f"Band {band_index} extracted successfully for both years.")
            QMessageBox.information(
                self.dialog, "Success", f"Band {band_index} extracted and background removed.")
        except Exception as e:
            self.log_message(f"Error extracting band: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error extracting band: {str(e)}")

    def open_histogram(self):
        print("open_histogram called")
        if not self.band_year1_path or not self.band_year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please extract the bands first.")
            return
        try:
            ds1 = gdal.Open(self.band_year1_path)
            ds2 = gdal.Open(self.band_year2_path)
            band1 = ds1.GetRasterBand(1).ReadAsArray()
            band2 = ds2.GetRasterBand(1).ReadAsArray()
            ds1 = None
            ds2 = None

            dialog = QDialog(self.dialog)
            dialog.setWindowTitle("Contrast Adjustment - Histogram")
            layout = QVBoxLayout()
            dialog.setLayout(layout)

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            ax1.hist(band1[~np.isnan(band1)].flatten(),
                     bins=256, color='blue', alpha=0.7)
            ax1.set_title('Histogram - Year 1')
            ax2.hist(band2[~np.isnan(band2)].flatten(),
                     bins=256, color='green', alpha=0.7)
            ax2.set_title('Histogram - Year 2')
            plt.tight_layout()
            canvas = FigureCanvas(fig)
            # add navigation toolbar so user can pan/zoom the histogram
            try:
                toolbar = NavigationToolbar(canvas, dialog)
                layout.addWidget(toolbar)
            except Exception:
                pass
            layout.addWidget(canvas)
            # 1. Carrega as bandas
            ds1 = gdal.Open(self.band_year1_path)
            ds2 = gdal.Open(self.band_year2_path)
            band1 = ds1.GetRasterBand(1).ReadAsArray()
            band2 = ds2.GetRasterBand(1).ReadAsArray()

            # 2. Detecta o valor máximo da banda para definir o range do slider
            max_val = int(max(np.nanmax(band1) if not np.all(np.isnan(band1)) else 0,
                              np.nanmax(band2) if not np.all(np.isnan(band2)) else 0))
            
            # Se o valor máximo for maior que 255, usa 65535 como limite superior para o slider
            # Caso contrário, usa 255.
            slider_max = 65535 if max_val > 255 else 255
            self.log_message(f"Detected max band value: {max_val}. Setting slider max to: {slider_max}")

            # Min Year 1 - Label, Slider e SpinBox
            min1_label = QLabel("Min Year 1:")
            min1_slider = QSlider(Qt.Horizontal)
            min1_slider.setRange(0, slider_max)
            min1_slider.setValue(int(np.nanmin(band1))
                                 if not np.all(np.isnan(band1)) else 0)
            min1_spinbox = QSpinBox()
            min1_spinbox.setRange(0, slider_max)
            min1_spinbox.setValue(min1_slider.value())

            # Sincronização bidirecional
            min1_slider.valueChanged.connect(min1_spinbox.setValue)
            min1_spinbox.valueChanged.connect(min1_slider.setValue)

            # Layout horizontal para slider e spinbox
            min1_layout = QHBoxLayout()
            min1_layout.addWidget(min1_slider)
            min1_layout.addWidget(min1_spinbox)

            layout.addWidget(min1_label)
            layout.addLayout(min1_layout)

            # Max Year 1 - Label, Slider e SpinBox
            max1_label = QLabel("Max Year 1:")
            max1_slider = QSlider(Qt.Horizontal)
            max1_slider.setRange(0, slider_max)
            max1_slider.setValue(int(np.nanmax(band1))
                                 if not np.all(np.isnan(band1)) else slider_max)
            max1_spinbox = QSpinBox()
            max1_spinbox.setRange(0, slider_max)
            max1_spinbox.setValue(max1_slider.value())

            # Sincronização bidirecional
            max1_slider.valueChanged.connect(max1_spinbox.setValue)
            max1_spinbox.valueChanged.connect(max1_slider.setValue)

            # Layout horizontal para slider e spinbox
            max1_layout = QHBoxLayout()
            max1_layout.addWidget(max1_slider)
            max1_layout.addWidget(max1_spinbox)

            layout.addWidget(max1_label)
            layout.addLayout(max1_layout)

            # Min Year 2 - Label, Slider e SpinBox
            min2_label = QLabel("Min Year 2:")
            min2_slider = QSlider(Qt.Horizontal)
            min2_slider.setRange(0, slider_max)
            min2_slider.setValue(int(np.nanmin(band2))
                                 if not np.all(np.isnan(band2)) else 0)
            min2_spinbox = QSpinBox()
            min2_spinbox.setRange(0, slider_max)
            min2_spinbox.setValue(min2_slider.value())

            # Sincronização bidirecional
            min2_slider.valueChanged.connect(min2_spinbox.setValue)
            min2_spinbox.valueChanged.connect(min2_slider.setValue)

            # Layout horizontal para slider e spinbox
            min2_layout = QHBoxLayout()
            min2_layout.addWidget(min2_slider)
            min2_layout.addWidget(min2_spinbox)

            layout.addWidget(min2_label)
            layout.addLayout(min2_layout)

            # Max Year 2 - Label, Slider e SpinBox
            max2_label = QLabel("Max Year 2:")
            max2_slider = QSlider(Qt.Horizontal)
            max2_slider.setRange(0, slider_max)
            max2_slider.setValue(int(np.nanmax(band2))
                                 if not np.all(np.isnan(band2)) else slider_max)
            max2_spinbox = QSpinBox()
            max2_spinbox.setRange(0, slider_max)
            max2_spinbox.setValue(max2_slider.value())

            # Sincronização bidirecional
            max2_slider.valueChanged.connect(max2_spinbox.setValue)
            max2_spinbox.valueChanged.connect(max2_slider.setValue)

            # Layout horizontal para slider e spinbox
            max2_layout = QHBoxLayout()
            max2_layout.addWidget(max2_slider)
            max2_layout.addWidget(max2_spinbox)

            layout.addWidget(max2_label)
            layout.addLayout(max2_layout)

            fig_prev, (ax_prev1, ax_prev2) = plt.subplots(
                1, 2, figsize=(12, 5))
            canvas_prev = FigureCanvas(fig_prev)
            # add toolbar for preview so zoom works
            try:
                toolbar_prev = NavigationToolbar(canvas_prev, dialog)
                layout.addWidget(toolbar_prev)
            except Exception:
                pass
            layout.addWidget(QLabel("Normalization Preview:"))
            layout.addWidget(canvas_prev)

            def update_preview():
                norm1 = np.clip((band1 - min1_slider.value()) /
                                (max1_slider.value() - min1_slider.value() + 1e-6) * 255, 0, 255)
                norm2 = np.clip((band2 - min2_slider.value()) /
                                (max2_slider.value() - min2_slider.value() + 1e-6) * 255, 0, 255)
                ax_prev1.clear()
                ax_prev1.imshow(norm1, cmap='gray')
                ax_prev1.set_title('Preview Year 1', fontsize=10)
                ax_prev2.clear()
                ax_prev2.imshow(norm2, cmap='gray')
                ax_prev2.set_title('Preview Year 2', fontsize=10)
                canvas_prev.draw()

            min1_slider.valueChanged.connect(update_preview)
            max1_slider.valueChanged.connect(update_preview)
            min2_slider.valueChanged.connect(update_preview)
            max2_slider.valueChanged.connect(update_preview)

            preview_button = QPushButton("Update Preview")
            preview_button.clicked.connect(update_preview)
            layout.addWidget(preview_button)

            def apply_normalization():
                self.normalize_contrast(
                    min1_slider.value(), max1_slider.value(),
                    min2_slider.value(), max2_slider.value()
                )
                dialog.accept()

            apply_button = QPushButton("Apply Normalization and Close")
            apply_button.clicked.connect(apply_normalization)
            layout.addWidget(apply_button)

            update_preview()
            dialog.exec_()
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error in open_histogram: {str(e)}", 'UrbanChangeAid', Qgis.Warning)
            QMessageBox.warning(self.dialog, "Error",
                                f"Error generating histogram: {str(e)}")

    def normalize_contrast(self, min1=None, max1=None, min2=None, max2=None):
        if not self.band_year1_path or not self.band_year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please extract bands first.")
            return
        try:
            output_dir = os.path.join(self.temp_dir, "normalized_bands")
            os.makedirs(output_dir, exist_ok=True)
            self.norm_year1_path = os.path.join(output_dir, "norm_year1.tif")
            self.norm_year2_path = os.path.join(output_dir, "norm_year2.tif")

            ds1 = gdal.Open(self.band_year1_path)
            ds2 = gdal.Open(self.band_year2_path)
            band1 = ds1.GetRasterBand(1).ReadAsArray()
            band2 = ds2.GetRasterBand(1).ReadAsArray()

            if min1 is None:
                min1 = np.nanmin(band1)
            if max1 is None:
                max1 = np.nanmax(band1)
            if min2 is None:
                min2 = np.nanmin(band2)
            if max2 is None:
                max2 = np.nanmax(band2)

            norm1 = np.clip((band1 - min1) / (max1 - min1 + 1e-6)
                            * 255, 0, 255).astype(np.uint8)
            norm2 = np.clip((band2 - min2) / (max2 - min2 + 1e-6)
                            * 255, 0, 255).astype(np.uint8)

            norm1[np.isnan(band1)] = 0
            norm2[np.isnan(band2)] = 0

            driver = gdal.GetDriverByName('GTiff')
            out1 = driver.Create(
                self.norm_year1_path, ds1.RasterXSize, ds1.RasterYSize, 1, gdal.GDT_Byte)
            out1.SetGeoTransform(ds1.GetGeoTransform())
            out1.SetProjection(ds1.GetProjection())
            out1.GetRasterBand(1).WriteArray(norm1)
            out1.FlushCache()
            out1 = None

            out2 = driver.Create(
                self.norm_year2_path, ds2.RasterXSize, ds2.RasterYSize, 1, gdal.GDT_Byte)
            out2.SetGeoTransform(ds2.GetGeoTransform())
            out2.SetProjection(ds2.GetProjection())
            out2.GetRasterBand(1).WriteArray(norm2)
            out2.FlushCache()
            out2 = None

            ds1 = None
            ds2 = None

            self._load_to_project(self.norm_year1_path, "Normalized - Year 1")
            self._load_to_project(self.norm_year2_path, "Normalized - Year 2")
            self.log_message("Contrast normalized successfully.")
            QMessageBox.information(
                self.dialog, "Success", "Contrast normalized successfully.")
        except Exception as e:
            self.log_message(f"Error normalizing contrast: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error normalizing contrast: {str(e)}")

    def extract_and_normalize_with_reset(self):
        self.extract_band()
        if self.band_year1_path and self.band_year2_path:
            self.normalize_contrast()

    def next_to_binarization(self):
        if self.norm_year1_path and self.norm_year2_path:
            self.dialog.tabWidget.setTabEnabled(3, True)
            self.dialog.tabWidget.setCurrentIndex(3)
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please normalize the contrast first.")

    def binarize(self):
        """Binarize the normalized images based on threshold values."""
        if not self.band_year1_path or not self.band_year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please extract bands first.")
            return
        try:
            output_dir = os.path.join(self.temp_dir, "binarized_images")
            os.makedirs(output_dir, exist_ok=True)
            self.bin_year1_path = os.path.join(output_dir, "bin_year1.tif")
            self.bin_year2_path = os.path.join(output_dir, "bin_year2.tif")

            ds1 = gdal.Open(self.band_year1_path)
            if ds1 is None:
                raise Exception(
                    f"Failed to open band image for Year 1: {self.band_year1_path}")
            data1 = ds1.ReadAsArray()
            threshold1 = self.dialog.spinThresholdYear1.value()
            self.log_message(f"Binarize Year 1: Threshold={threshold1}, Max Data={np.nanmax(data1)}")
            bin_data1 = (data1 > self.dialog.spinThresholdYear1.value()).astype(
                np.uint8) * 255
            driver = gdal.GetDriverByName('GTiff')
            out_ds1 = driver.Create(
                self.bin_year1_path, ds1.RasterXSize, ds1.RasterYSize, 1, gdal.GDT_Byte)
            out_ds1.SetGeoTransform(ds1.GetGeoTransform())
            out_ds1.SetProjection(ds1.GetProjection())
            out_ds1.GetRasterBand(1).WriteArray(bin_data1)
            out_ds1 = None
            ds1 = None

            ds2 = gdal.Open(self.band_year2_path)
            if ds2 is None:
                raise Exception(
                    f"Failed to open band image for Year 2: {self.band_year2_path}")
            data2 = ds2.ReadAsArray()
            threshold2 = self.dialog.spinThresholdYear2.value()
            self.log_message(f"Binarize Year 2: Threshold={threshold2}, Max Data={np.nanmax(data2)}")
            bin_data2 = (data2 > self.dialog.spinThresholdYear2.value()).astype(
                np.uint8) * 255
            out_ds2 = driver.Create(
                self.bin_year2_path, ds2.RasterXSize, ds2.RasterYSize, 1, gdal.GDT_Byte)
            out_ds2.SetGeoTransform(ds2.GetGeoTransform())
            out_ds2.SetProjection(ds2.GetProjection())
            out_ds2.GetRasterBand(1).WriteArray(bin_data2)
            out_ds2 = None
            ds2 = None

            import traceback

            # Diagnostics for Year 1
            exists1 = os.path.exists(self.bin_year1_path)
            valid1 = False
            try:
                valid1 = QgsRasterLayer(self.bin_year1_path, "").isValid()
            except Exception:
                valid1 = False
            self.log_message(f"Diagnostics Year1 - path_exists={exists1}, qgs_valid={valid1}")
            if exists1 and valid1:
                try:
                    self._load_to_project(self.bin_year1_path, "Binarized - Year 1")
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error loading Binarized - Year 1: {e}\n{traceback.format_exc()}", 'UrbanChangeAid', Qgis.Warning)
                    raise
            else:
                raise Exception("Failed to create binarized image for Year 1.")

            # Diagnostics for Year 2
            exists2 = os.path.exists(self.bin_year2_path)
            valid2 = False
            try:
                valid2 = QgsRasterLayer(self.bin_year2_path, "").isValid()
            except Exception:
                valid2 = False
            self.log_message(f"Diagnostics Year2 - path_exists={exists2}, qgs_valid={valid2}")
            if exists2 and valid2:
                try:
                    self._load_to_project(self.bin_year2_path, "Binarized - Year 2")
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error loading Binarized - Year 2: {e}\n{traceback.format_exc()}", 'UrbanChangeAid', Qgis.Warning)
                    raise
            else:
                raise Exception("Failed to create binarized image for Year 2.")
            QMessageBox.information(
                self.dialog, "Success", "Images binarized successfully.")
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Binarize error: {str(e)} - Check norm paths: {self.norm_year1_path}, {self.norm_year2_path}", 'UrbanChangeAid', Qgis.Warning)
            QMessageBox.warning(self.dialog, "Error",
                                f"Error binarizing images: {str(e)}")

    def next_to_sieve(self):
        """Navigate to the Sieve tab if binarization is complete."""
        if self.bin_year1_path and self.bin_year2_path:
            self.dialog.tabWidget.setTabEnabled(4, True)
            self.dialog.tabWidget.setCurrentIndex(4)
            self.log_message("Navigated to Sieve tab.")
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please binarize the images first.")

    def apply_sieve(self):
        if not self.bin_year1_path or not self.bin_year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please binarize images first.")
            return

        if not self.dialog.chkApplySieve.isChecked():
            self.log_message("Sieve not applied (unchecked).")
            return

        threshold = self.dialog.spinSieveThreshold.value()
        try:
            self.sieved_year1_path = os.path.join(
                self.temp_dir, "sieved_year1.tif")
            self.sieved_year2_path = os.path.join(
                self.temp_dir, "sieved_year2.tif")

            processing.run("gdal:sieve", {
                'INPUT': self.bin_year1_path,
                'THRESHOLD': threshold,
                'OUTPUT': self.sieved_year1_path,
                'CONNECTIVITY': 8
            })

            processing.run("gdal:sieve", {
                'INPUT': self.bin_year2_path,
                'THRESHOLD': threshold,
                'OUTPUT': self.sieved_year2_path,
                'CONNECTIVITY': 8
            })

            self.sieve_applied = True
            self._load_to_project(self.sieved_year1_path, "Sieved Year 1")
            self._load_to_project(self.sieved_year2_path, "Sieved Year 2")
            QMessageBox.information(
                self.dialog, "Success", "Sieve applied successfully.")
        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error applying sieve: {str(e)}")

    def next_to_diff(self):
        QgsMessageLog.logMessage(
            "next_to_diff called", 'UrbanChangeAid', Qgis.Info)
        has_inputs = False
        if ((hasattr(self, 'sieved_year1_path') and self.sieved_year1_path and os.path.exists(self.sieved_year1_path)) or (self.bin_year1_path and os.path.exists(self.bin_year1_path))):
            if ((hasattr(self, 'sieved_year2_path') and self.sieved_year2_path and os.path.exists(self.sieved_year2_path)) or (self.bin_year2_path and os.path.exists(self.bin_year2_path))):
                has_inputs = True
        if has_inputs:
            self.dialog.tabWidget.setTabEnabled(5, True)
            self.dialog.tabWidget.setCurrentIndex(5)
            self.log_message("Navigated to Difference Calculation tab.")
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please binarize or sieve the images first.")

        # Debug: veja no log se o botão chama isso
        QgsMessageLog.logMessage(
            "next_to_diff called", 'UrbanChangeAid', Qgis.Info)
        if self.bin_year1_path and self.bin_year2_path:
            self.dialog.tabWidget.setTabEnabled(5, True)
            self.dialog.tabWidget.setCurrentIndex(5)
            self.log_message("Navigated to Difference Calculation tab.")
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please binarize the images first.")

    def calculate_difference(self):
        """Calculate difference image. Accepts either sieved (if present) or binarized images."""
        # Decide which inputs to use: prefer sieved if available, else binarized
        year1_path = None
        year2_path = None

        if hasattr(self, 'sieved_year1_path') and self.sieved_year1_path and os.path.exists(self.sieved_year1_path):
            year1_path = self.sieved_year1_path
        elif self.bin_year1_path and os.path.exists(self.bin_year1_path):
            year1_path = self.bin_year1_path

        if hasattr(self, 'sieved_year2_path') and self.sieved_year2_path and os.path.exists(self.sieved_year2_path):
            year2_path = self.sieved_year2_path
        elif self.bin_year2_path and os.path.exists(self.bin_year2_path):
            year2_path = self.bin_year2_path

        if not year1_path or not year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please binarize or sieve images first.")
            return

        if year1_path == year2_path:
            self.log_message(
                "Warning: Year 1 and Year 2 inputs are the same - difference will be zero.")
            QMessageBox.warning(
                self.dialog, "Warning", "Selected Year 1 and Year 2 inputs are the same. Difference will be zero.")
            return

        self.log_message(f"Using Year 1: {year1_path}, Year 2: {year2_path}")
        try:
            output_dir = os.path.join(self.temp_dir, "difference_images")
            os.makedirs(output_dir, exist_ok=True)
            self.difference_path = os.path.join(
                output_dir, "difference.tif")  # Use um nome consistente
            self.log_message(f"Output path set to: {self.difference_path}")

            # Try OTB MAD; fallback to simple raster diff if OTB not available
            try:
                self.log_message(
                    "Attempting OTB MultivariateAlterationDetector")
                processing.run("otb:MultivariateAlterationDetector", {
                    'in1': year1_path,
                    'in2': year2_path,
                    'out': self.difference_path,
                    'outputpixeltype': 2
                })
            except Exception as e_otb:
                self.log_message(
                    f"OTB failed: {str(e_otb)}. Falling back to simple difference.")
                ds1 = gdal.Open(year1_path)
                ds2 = gdal.Open(year2_path)
                if ds1 is None or ds2 is None:
                    self.log_message(
                        f"Failed to open images: Year1={year1_path}, Year2={year2_path}")
                    return
                arr1 = ds1.GetRasterBand(1).ReadAsArray().astype(np.float32)
                arr2 = ds2.GetRasterBand(1).ReadAsArray().astype(np.float32)
                if arr1.shape != arr2.shape:
                    self.log_message("Images have different dimensions.")
                    return
                ds1 = None
                ds2 = None
                diff_arr = (arr2 - arr1).astype(np.float32)
                driver = gdal.GetDriverByName('GTiff')
                out = driver.Create(
                    self.difference_path, diff_arr.shape[1], diff_arr.shape[0], 1, gdal.GDT_Float32)
                if out is None:
                    self.log_message(
                        f"Failed to create output: {self.difference_path}")
                    return
                out.SetGeoTransform(gdal.Open(year1_path).GetGeoTransform())
                out.SetProjection(gdal.Open(year1_path).GetProjection())
                out.GetRasterBand(1).WriteArray(diff_arr)
                out = None
                self.log_message("Fallback GDAL completed.")

            if os.path.exists(self.difference_path) and QgsRasterLayer(self.difference_path, "").isValid():
                self._load_to_project(self.difference_path, "Difference Image")
                self.log_message("Successfully calculated difference.")
                QMessageBox.information(
                    self.dialog, "Success", "Successfully calculated difference.")
            else:
                raise Exception("Failed to create difference image.")

        except Exception as e:
            self.log_message(f"Error calculating difference: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error calculating difference: {str(e)}")
            return

    def _apply_pseudo_color_renderer(self, layer, min_val=None, max_val=None):
        """Apply a three-color pseudo color renderer: losses (blue) at min, neutral (white) at 0, gains (red) at max.

        This preserves the original Float32 difference values in the raster and maps them for visualization.
        If min_val/max_val are not provided, attempt to read them from the raster on disk.
        """
        try:
            if layer is None or not isinstance(layer, QgsRasterLayer):
                self.log_message(
                    "_apply_pseudo_color_renderer: invalid layer provided.")
                return

            # If min/max not provided, read from raster
            if min_val is None or max_val is None:
                try:
                    src = layer.source() if hasattr(
                        layer, 'source') else layer.dataProvider().dataSourceUri()
                    ds = gdal.Open(src)
                    if ds is not None:
                        arr = ds.GetRasterBand(
                            1).ReadAsArray().astype(np.float32)
                        ds = None
                        min_val = float(
                            np.nanmin(arr)) if min_val is None else min_val
                        max_val = float(
                            np.nanmax(arr)) if max_val is None else max_val
                except Exception:
                    # leave min_val/max_val as-is (may still be None)
                    pass

            # Ensure numeric min/max
            if min_val is None or max_val is None or np.isnan(min_val) or np.isnan(max_val):
                self.log_message(
                    "_apply_pseudo_color_renderer: invalid min/max, aborting renderer application.")
                return

            # Avoid zero-range ramps
            if np.isclose(min_val, max_val):
                min_val = float(min_val) - 1.0
                max_val = float(max_val) + 1.0

            entries = []
            try:
                entries.append(QgsColorRampShader.ColorRampItem(
                    min_val, QColor(0, 0, 255), f"{min_val:.6f}"))
                # include neutral white at 0 if within range
                if min_val < 0.0 < max_val:
                    entries.append(QgsColorRampShader.ColorRampItem(
                        0.0, QColor(255, 255, 255), '0'))
                entries.append(QgsColorRampShader.ColorRampItem(
                    max_val, QColor(255, 0, 0), f"{max_val:.6f}"))
            except Exception:
                # Fallback: use normalized positions if something goes wrong
                entries = [QgsColorRampShader.ColorRampItem(0.0, QColor(0, 0, 255), 'min'),
                           QgsColorRampShader.ColorRampItem(
                               0.5, QColor(255, 255, 255), '0'),
                           QgsColorRampShader.ColorRampItem(1.0, QColor(255, 0, 0), 'max')]

            color_ramp = QgsColorRampShader()
            color_ramp.setColorRampItemList(entries)
            color_ramp.setColorRampType(QgsColorRampShader.Interpolated)

            raster_shader = QgsRasterShader()
            raster_shader.setRasterShaderFunction(color_ramp)

            renderer = QgsSingleBandPseudoColorRenderer(
                layer.dataProvider(), 1, raster_shader)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            self.log_message("Pseudo-color renderer applied (min/max).")
        except Exception as e:
            self.log_message(f"Error applying pseudo-color renderer: {e}")

    def next_to_gain_loss(self):
        if self.difference_path and os.path.exists(self.difference_path):
            tab_index = 6  # Índice da aba Gain & Loss Masks
            self.dialog.tabWidget.setTabEnabled(tab_index, True)
            self.dialog.tabWidget.setCurrentIndex(tab_index)
            self.log_message("Navegado para a aba Gain & Loss Masks.")
        else:
            QMessageBox.warning(
                self.dialog, "Warning", "Please compute the difference image first.")

    def show_gain_loss_dialog(self):
        has_bins = (
            self.bin_year1_path and os.path.exists(self.bin_year1_path) and
            self.bin_year2_path and os.path.exists(self.bin_year2_path)
        )
        has_diff = self.difference_path and os.path.exists(
            self.difference_path)
        if not (has_bins or has_diff):
            QMessageBox.warning(self.dialog, "Warning",
                                "Compute the difference or binarization first.")
            return

        dialog = QDialog(self.dialog)
        dialog.setWindowTitle("Gain and Loss Settings")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        # Gain threshold
        # Detecta o valor máximo da imagem de diferença
        diff_ds = gdal.Open(self.difference_path)
        diff_band = diff_ds.GetRasterBand(1).ReadAsArray()
        max_abs_val = np.nanmax(np.abs(diff_band))
        diff_ds = None
        
        # Define o range máximo para o spinbox (255.0 ou 65535.0)
        max_range = 65535.0 if max_abs_val > 255.0 else 255.0
        
        thresh_gain_spin = QDoubleSpinBox()
        thresh_gain_spin.setDecimals(2)
        thresh_gain_spin.setRange(-max_range, max_range)
        thresh_gain_spin.setSingleStep(0.10)
        thresh_gain_spin.setValue(0.10)
        layout.addWidget(QLabel("Gain Threshold:"))
        layout.addWidget(thresh_gain_spin)

        # Loss threshold
        thresh_loss_spin = QDoubleSpinBox()
        thresh_loss_spin.setDecimals(2)
        thresh_loss_spin.setRange(-max_range, max_range)
        thresh_loss_spin.setSingleStep(0.10)
        thresh_loss_spin.setValue(-0.10)
        layout.addWidget(QLabel("Loss Threshold:"))
        layout.addWidget(thresh_loss_spin)

        # Sieve threshold for cleaning isolated pixels
        layout.addWidget(QLabel("\nSieve Settings (for cleaning masks):"))
        sieve_threshold_spin = QSpinBox()
        sieve_threshold_spin.setRange(1, 1000)
        sieve_threshold_spin.setValue(8)
        sieve_threshold_spin.setToolTip(
            "Minimum number of connected pixels to keep. Smaller groups will be removed.")
        layout.addWidget(QLabel("Sieve Threshold (pixels):"))
        layout.addWidget(sieve_threshold_spin)

        apply_button = QPushButton("Generate Masks")

        def apply_and_close():
            self.generateMasks_with_params(
                thresh_gain_spin.value(),
                thresh_loss_spin.value()
            )
            dialog.accept()

        apply_button.clicked.connect(apply_and_close)
        layout.addWidget(apply_button)

        # Button to apply sieve to already generated masks
        apply_sieve_button = QPushButton("Clean Isolated Pixels (Apply Sieve)")
        apply_sieve_button.setToolTip(
            "Remove small isolated pixel groups from the generated masks")

        def apply_sieve_and_close():
            self.apply_sieve_to_masks(
                threshold=sieve_threshold_spin.value(),
                connectivity=8
            )

        apply_sieve_button.clicked.connect(apply_sieve_and_close)
        layout.addWidget(apply_sieve_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def generateMasks_with_params(self, thresh_gain=0.1, thresh_loss=-0.1):
        """Generate gain and loss masks from difference image with thresholds."""
        try:
            if not self.difference_path or not os.path.exists(self.difference_path):
                raise Exception("Difference image not found.")

            output_dir = os.path.join(self.temp_dir, "change_mask")
            os.makedirs(output_dir, exist_ok=True)
            self.gain_mask_path = os.path.join(output_dir, "gain_mask.tif")
            self.loss_mask_path = os.path.join(output_dir, "loss_mask.tif")

            ds = gdal.Open(self.difference_path)
            if ds is None:
                raise Exception("Failed to open difference image.")
            diff = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            geo = ds.GetGeoTransform()
            proj = ds.GetProjection()
            ds = None

            # Diagnostics
            try:
                finite_mask = np.isfinite(diff)
                total_pixels = diff.size
                finite_pixels = np.count_nonzero(finite_mask)
                minv = float(np.nanmin(diff)) if finite_pixels > 0 else float('nan')
                maxv = float(np.nanmax(diff)) if finite_pixels > 0 else float('nan')
                pct_finite = finite_pixels / total_pixels * 100.0 if total_pixels > 0 else 0.0
            except Exception:
                minv = float('nan')
                maxv = float('nan')
                pct_finite = 0.0
            self.log_message(f"Difference stats: min={minv}, max={maxv}, finite%={pct_finite:.2f}%, shape={diff.shape}")

            # If thresholds are inconsistent (e.g., user swapped gain/loss), fix by swapping
            try:
                if thresh_gain <= thresh_loss:
                    self.log_message(f"Warning: gain threshold ({thresh_gain}) <= loss threshold ({thresh_loss}). Swapping values.")
                    thresh_gain, thresh_loss = thresh_loss, thresh_gain
            except Exception:
                pass

            # Count how many pixels meet thresholds (for debugging when masks are all white/black)
            try:
                count_gain = int(np.count_nonzero((diff >= thresh_gain) & finite_mask))
                count_loss = int(np.count_nonzero((diff <= thresh_loss) & finite_mask))
            except Exception:
                count_gain = 0
                count_loss = 0
            self.log_message(f"Pixels >= gain({thresh_gain}): {count_gain} / {total_pixels}")
            self.log_message(f"Pixels <= loss({thresh_loss}): {count_loss} / {total_pixels}")

            # Generate masks robustly using finite mask
            gain = np.zeros_like(diff, dtype=np.uint8)
            loss = np.zeros_like(diff, dtype=np.uint8)
            if finite_pixels > 0:
                gain[np.where((diff >= thresh_gain) & finite_mask)] = 255
                loss[np.where((diff <= thresh_loss) & finite_mask)] = 255

            # Diagnostic outputs: save normalized diff and histogram for inspection
            try:
                # Ensure GDAL driver is available for debug writes
                driver = gdal.GetDriverByName('GTiff')
                debug_dir = output_dir
                diff_debug_path = os.path.join(debug_dir, "diff_debug.tif")
                hist_path = os.path.join(debug_dir, "diff_hist.png")
                # normalize diff to 0-255 for visualization (finite only)
                norm = np.zeros_like(diff, dtype=np.uint8)
                if np.isfinite(minv) and np.isfinite(maxv) and not np.isclose(minv, maxv):
                    scaled = (diff - minv) / (maxv - minv)
                    scaled[~finite_mask] = 0.0
                    norm = np.clip((scaled * 255.0), 0, 255).astype(np.uint8)
                else:
                    # fallback: cast finite values to 255
                    norm[finite_mask] = 255

                try:
                    dbg_ds = driver.Create(diff_debug_path, norm.shape[1], norm.shape[0], 1, gdal.GDT_Byte)
                    dbg_ds.SetGeoTransform(geo)
                    dbg_ds.SetProjection(proj)
                    dbg_ds.GetRasterBand(1).WriteArray(norm)
                    dbg_ds.FlushCache()
                    dbg_ds = None
                    self.log_message(f"Wrote diagnostic diff image: {diff_debug_path}")
                except Exception as e:
                    self.log_message(f"Failed to write diff_debug.tif: {e}")

                # save histogram of finite diff values
                try:
                    vals = diff[finite_mask]
                    if vals.size > 0:
                        plt.figure(figsize=(6, 4))
                        plt.hist(vals.flatten(), bins=256)
                        plt.title('Difference Histogram')
                        plt.tight_layout()
                        plt.savefig(hist_path)
                        plt.close()
                        self.log_message(f"Wrote diagnostic histogram: {hist_path}")
                except Exception as e:
                    self.log_message(f"Failed to write histogram: {e}")
            except Exception:
                pass

            # Ensure driver is available for subsequent raster writes
            driver = gdal.GetDriverByName('GTiff')
            out_g = driver.Create(
                self.gain_mask_path, gain.shape[1], gain.shape[0], 1, gdal.GDT_Byte)
            out_g.SetGeoTransform(geo)
            out_g.SetProjection(proj)
            out_g.GetRasterBand(1).WriteArray(gain)
            try:
                out_g.GetRasterBand(1).SetNoDataValue(0)
            except Exception:
                pass
            out_g.FlushCache()
            out_g = None

            out_l = driver.Create(
                self.loss_mask_path, loss.shape[1], loss.shape[0], 1, gdal.GDT_Byte)
            out_l.SetGeoTransform(geo)
            out_l.SetProjection(proj)
            out_l.GetRasterBand(1).WriteArray(loss)
            try:
                out_l.GetRasterBand(1).SetNoDataValue(0)
            except Exception:
                pass
            out_l.FlushCache()
            out_l = None

            # Load masks into QGIS project so they are visible and paths are set
            self._load_to_project(self.gain_mask_path, "Gain Mask")
            self._load_to_project(self.loss_mask_path, "Loss Mask")

            self.log_message(
                f"Masks generated and loaded: gain={thresh_gain}, loss={thresh_loss}")
            QMessageBox.information(
                self.dialog, "Success", "Masks successfully generated and loaded into project.")

        except Exception as e:
            self.log_message(f"Error generating masks: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error generating masks: {str(e)}")

    def apply_sieve_to_masks(self, threshold=8, connectivity=8):
        """Apply sieve filter directly to the generated gain/loss masks."""
        if not self.gain_mask_path or not self.loss_mask_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please generate the masks first.")
            return

        if not os.path.exists(self.gain_mask_path) or not os.path.exists(self.loss_mask_path):
            QMessageBox.warning(self.dialog, "Warning",
                                "Mask files not found. Generate them first.")
            return

        try:
            output_dir = os.path.join(self.temp_dir, "sieved_masks")
            os.makedirs(output_dir, exist_ok=True)

            self.sieved_gain_mask_path = os.path.join(
                output_dir, "gain_mask_sieved.tif")
            self.sieved_loss_mask_path = os.path.join(
                output_dir, "loss_mask_sieved.tif")

            # Run sieve for gain
            processing.run("gdal:sieve", {
                'INPUT': self.gain_mask_path,
                'THRESHOLD': threshold,
                'CONNECTIVITY': connectivity,
                'OUTPUT': self.sieved_gain_mask_path
            })

            # Run sieve for loss
            processing.run("gdal:sieve", {
                'INPUT': self.loss_mask_path,
                'THRESHOLD': threshold,
                'CONNECTIVITY': connectivity,
                'OUTPUT': self.sieved_loss_mask_path
            })

            # Load sieved masks into project
            if hasattr(self, "_load_to_project"):
                self._load_to_project(
                    self.sieved_gain_mask_path, f"Gain Mask (Sieved ≥{threshold}px)")
                self._load_to_project(
                    self.sieved_loss_mask_path, f"Loss Mask (Sieved ≥{threshold}px)")

            QMessageBox.information(
                self.dialog, "Success", f"Sieve applied with threshold={threshold}, connectivity={connectivity}.")
            self.log_message(
                f"Sieve applied to Gain/Loss masks with threshold={threshold}, connectivity={connectivity}.")

        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error applying sieve to masks: {str(e)}")
            self.log_message(f"Error applying sieve: {str(e)}")

    def nextToVector(self):
        have_gain = self.gain_mask_path and os.path.exists(self.gain_mask_path)
        have_loss = self.loss_mask_path and os.path.exists(self.loss_mask_path)
        if have_gain or have_loss:
            # "Vectorization" é a 8ª aba -> índice 7
            self.dialog.tabWidget.setTabEnabled(7, True)
            self.dialog.tabWidget.setCurrentIndex(7)
        else:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please generate gain/loss masks first.")

    def on_generate_gain_loss_clicked(self):
        """Slot connected to the button in the UI. Opens the Gain/Loss settings dialog."""
        self.show_gain_loss_dialog()

        def _remove_background_features(self, vector_path, field_name, value_to_remove):
            """Remove feições de um shapefile onde o campo especificado tem o valor especificado."""
            try:
                layer = QgsVectorLayer(vector_path, os.path.basename(vector_path), "ogr")
                if not layer.isValid():
                    self.log_message(f"Falha ao carregar layer para remoção de background: {vector_path}")
                    return

                if not layer.startEditing():
                    self.log_message(f"Falha ao iniciar edição para remoção de background: {vector_path}")
                    return

                ids_to_delete = []
                for feature in layer.getFeatures():
                    if feature[field_name] == value_to_remove:
                        ids_to_delete.append(feature.id())

                if ids_to_delete:
                    layer.deleteFeatures(ids_to_delete)
                    layer.commitChanges()
                    self.log_message(f"Removidas {len(ids_to_delete)} feições de background (valor {value_to_remove} no campo '{field_name}') de {os.path.basename(vector_path)}")
                else:
                    layer.rollBack()
                self.log_message(f"Nenhuma feição de background encontrada para remoção em {os.path.basename(vector_path)}")

            except Exception as e:
                self.log_message(f"Erro ao remover feições de background em {vector_path}: {str(e)}")
                try:
                    layer.rollBack()
                except Exception:
                    pass

    def vectorize_and_orthogonalize(self):
        """Vetoriza as máscaras de ganho/perda (usa as sieved se existirem)."""
        gain_input = (
            self.sieved_gain_mask_path
            if hasattr(self, "sieved_gain_mask_path") and self.sieved_gain_mask_path and os.path.exists(self.sieved_gain_mask_path)
            else self.gain_mask_path
        )
        loss_input = (
            self.sieved_loss_mask_path
            if hasattr(self, "sieved_loss_mask_path") and self.sieved_loss_mask_path and os.path.exists(self.sieved_loss_mask_path)
            else self.loss_mask_path
        )

        if not (gain_input or loss_input):
            QMessageBox.warning(self.dialog, "Warning",
                                "Please generate gain/loss masks first.")
            return

        try:
            output_dir = os.path.join(self.temp_dir, "vectorized_results")
            os.makedirs(output_dir, exist_ok=True)

            if gain_input and os.path.exists(gain_input):
                self.gain_vector_path = os.path.join(
                    output_dir, "gain_vector.shp")
                processing.run("gdal:polygonize", {
                    "INPUT": gain_input,
                    "BAND": 1,
                    "FIELD": "val",
                    "OUTPUT": self.gain_vector_path
                }, is_child_algorithm=True)
                self._remove_background_features(self.gain_vector_path, "val", 0)
                self._load_vector_to_project(
                    self.gain_vector_path, "Gain Vector")

            if loss_input and os.path.exists(loss_input):
                self.loss_vector_path = os.path.join(
                    output_dir, "loss_vector.shp")
                processing.run("gdal:polygonize", {
                    "INPUT": loss_input,   # ✅ corrigido
                    "BAND": 1,
                    "FIELD": "val",
                    "OUTPUT": self.loss_vector_path
                }, is_child_algorithm=True)
                self._remove_background_features(self.loss_vector_path, "val", 0)
                self._load_vector_to_project(self.loss_vector_path, "Loss Vector")

            QMessageBox.information(
                self.dialog, "Success", "Masks vectorized successfully.")

        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error vectorizing: {str(e)}")

    def _load_vector_to_project(self, path, name):
        """Load a vector layer to the QGIS project, removing duplicates."""
        if not os.path.exists(path):
            self.log_message(f"Vector file does not exist: {path}")
            return None

        layer = QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            self.log_message(f"Invalid vector layer: {name}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Failed to load vector layer: {name}")
            return None

        # Remove existing layers with the same name
        existing_layers = QgsProject.instance().mapLayersByName(name)
        for ex_layer in existing_layers:
            QgsProject.instance().removeMapLayer(ex_layer.id())
            if ex_layer.id() in self.loaded_layer_ids:
                self.loaded_layer_ids.remove(ex_layer.id())

        # Add the new layer
        # Adiciona a camada ao projeto
        QgsProject.instance().addMapLayer(layer)

        # Configura o renderer para máscaras binárias (Gain/Loss)
        if "Binarized" in name or "Mask" in name:
            # Cria um renderer de banda única cinza com range 0-255
            renderer = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
            # Define o range de visualização fixo para 0 a 255

            ce = None
            try:
                ce = renderer.contrastEnhancement()
            except Exception:
                ce = None
            if ce is None:
                try:
                    from qgis.core import QgsContrastEnhancement

                    ce = QgsContrastEnhancement()
                    if hasattr(renderer, 'setContrastEnhancement'):
                        try:
                            renderer.setContrastEnhancement(ce)
                        except Exception:
                            pass
                except Exception:
                    ce = None
            if ce is not None:
                try:
                    ce.setMinimumValue(0)
                    ce.setMaximumValue(255)
                except Exception:
                    pass
            layer.setRenderer(renderer)
            layer.triggerRepaint()
        self.loaded_layer_ids.append(layer.id())
        self.log_message(f"Vector layer loaded: {name}")
        return layer

    def reproject_gain_loss_to_utm(self):
        """Reprojeta os vetores de ganho/perda para UTM e salva shapefiles."""
        try:
            if not self.gain_vector_path or not self.loss_vector_path:
                QMessageBox.warning(
                    self.dialog, "Warning", "Please vectorize the gain/loss masks first.")
                return

            output_dir = os.path.join(self.temp_dir, "vectors_utm")
            os.makedirs(output_dir, exist_ok=True)

            self.gain_vector_utm_path = os.path.join(
                output_dir, "gain_vector_utm.shp")
            self.loss_vector_utm_path = os.path.join(
                output_dir, "loss_vector_utm.shp")

            # reprojeta Gain
            processing.run("qgis:reprojectlayer", {
                "INPUT": self.gain_vector_path,
                # UTM S zone 23 (ajuste se necessário)
                "TARGET_CRS": "EPSG:32723",
                "OUTPUT": self.gain_vector_utm_path
            })

            # reprojeta Loss
            processing.run("qgis:reprojectlayer", {
                "INPUT": self.loss_vector_path,
                "TARGET_CRS": "EPSG:32723",
                "OUTPUT": self.loss_vector_utm_path
            })

            self._load_vector_to_project(
                self.gain_vector_utm_path, "Gain Vector UTM")
            self._load_vector_to_project(
                self.loss_vector_utm_path, "Loss Vector UTM")

            QMessageBox.information(
                self.dialog, "Success", "Vectors reprojected to UTM and loaded into the project.")

        except Exception as e:
            QMessageBox.warning(self.dialog, "Error",
                                f"Error reprojecting vectors: {str(e)}")

    def next_to_metrics(self):
        """Abre a aba Metrics carregando diretamente os vetores UTM exportados."""
        if not hasattr(self, 'gain_vector_utm_path') or not os.path.exists(self.gain_vector_utm_path):
            QMessageBox.warning(
                self.dialog, "Warning", "Please reproject the vectors first in the Vectorize tab.")
            return

        # Remove camadas duplicadas usando IDs para evitar invalidação
        for name in ["Gain Vector UTM", "Loss Vector UTM"]:
            existing_layers = QgsProject.instance().mapLayersByName(name)
            layer_ids_to_remove = [layer.id() for layer in existing_layers]
            for layer_id in layer_ids_to_remove:
                if layer_id in self.loaded_layer_ids:
                    QgsProject.instance().removeMapLayer(layer_id)
                    self.loaded_layer_ids.remove(layer_id)
                    self.log_message(
                        f"Removed duplicate layer with ID {layer_id} from QGIS project for {name} (files on disk are not deleted)")

        # Habilita a aba Metrics (avança uma aba a partir da posição atual)
        tw = getattr(self.dialog, 'tabWidget', None)
        if tw:
            cur = tw.currentIndex()
            next_index = cur + 1
            if next_index < tw.count():
                tw.setTabEnabled(next_index, True)
                tw.setCurrentIndex(next_index)

        # Carrega vetores UTM para edição
        self.gain_layer = QgsVectorLayer(
            self.gain_vector_utm_path, "Gain Vector UTM", "ogr")
        self.loss_layer = QgsVectorLayer(
            self.loss_vector_utm_path, "Loss Vector UTM", "ogr")

        # Define os campos de métricas com tipos explícitos
        metric_fields = {
            "area": float,  # Tipo float implícito
            "perimeter": float,
            "elongation": float,
            "rectang": float
        }

        for layer in [self.gain_layer, self.loss_layer]:
            if not layer.isValid():
                QMessageBox.warning(self.dialog, "Error",
                                    f"Failed to load layer {layer.name()}")
                return

            if not layer.isEditable():
                if not layer.startEditing():
                    raise Exception(
                        f"Could not start editing on {layer.name()}")

            provider = layer.dataProvider()
            existing_fields = [f.name() for f in provider.fields()]
            needed = []
            for name in metric_fields.keys():
                if name not in existing_fields:
                    # Tenta QVariant.Double como fallback
                    needed.append(QgsField(name, QVariant.Double))
            if needed:
                if not provider.addAttributes(needed):
                    raise Exception(
                        f"Failed to add attributes to {layer.name()}")
                layer.updateFields()
                self.log_message(
                    f"Added fields to {layer.name()}: {', '.join([f.name() for f in needed])}")

            # Garante que o diretório temporário exista e tenta exportar os vetores filtrados
            # para que o processamento subsequente possa usá-los.
            self._ensure_temp_dir()
            self._export_filtered_vectors_to_temp_fixed()
            layer = self.compute_metrics_on_layer(layer, layer.name())

        # Adiciona ao projeto após processamento
        QgsProject.instance().addMapLayers([self.gain_layer, self.loss_layer])
        self.loaded_layer_ids.extend(
            [self.gain_layer.id(), self.loss_layer.id()])

        # Config sliders (somente se ainda existirem no UI)
        for field in ["Area", "Perimeter", "Elongation", "Rectangularity"]:
            slider_attr = f"slider{field}"
            label_attr = f"labelMin{field}" if field != "Elongation" else "labelMaxElongation"

            if hasattr(self.dialog, slider_attr):
                slider = getattr(self.dialog, slider_attr)
                if field in ["Elongation", "Rectangularity"]:
                    slider.setRange(10, 100)
                else:
                    slider.setRange(1, 100000)

            if hasattr(self.dialog, label_attr):
                label = getattr(self.dialog, label_attr)
                label.setText(f"{field} sliders removed in this version.")

        if hasattr(self.dialog, 'labelMinArea'):
            self.dialog.labelMinArea.setText(
                f"Min area: {self.dialog.sliderArea.value():,}")
        if hasattr(self.dialog, 'labelMinPerimeter'):
            self.dialog.labelMinPerimeter.setText(
                f"Min perimeter: {self.dialog.sliderPerimeter.value():,}")
        if hasattr(self.dialog, 'labelMaxElongation'):
            self.dialog.labelMaxElongation.setText(
                f"Max elongation: {self.dialog.sliderElongation.value()/10:.1f}")
        if hasattr(self.dialog, 'labelMinRectangularity'):
            self.dialog.labelMinRectangularity.setText(
                f"Min rectang: {self.dialog.sliderRectangularity.value()/100:.2f}")

        QMessageBox.information(
            self.dialog, "Metrics", "Metrics computed and layers updated. Adjust filters with sliders.")
        self.log_message("Navigated to Metrics tab and prepared layers.")

    # funções antigas substituídas, não usam mais combos

    def load_gain_vector(self):
        """
        Obsoleto: combos foram removidos.
        Mantido apenas para evitar erros caso seja chamado.
        """
        if not hasattr(self, 'gain_vector_utm_path') or not os.path.exists(self.gain_vector_utm_path):
            QMessageBox.warning(
                self.dialog, "Warning", "Please reproject the vectors first in the Vectorize tab.")
            return

        self.gain_layer = self.ensure_fields(
            self.gain_vector_utm_path, "Gain Vector UTM")
        if self.gain_layer:
            QgsProject.instance().addMapLayer(self.gain_layer)
            self.log_message(
                "Gain Vector UTM loaded via load_gain_vector (compatibility).")

    def load_loss_vector(self):
        """
        Obsoleto: combos foram removidos.
        Mantido apenas para evitar erros caso seja chamado.
        """
        if not hasattr(self, 'loss_vector_utm_path') or not os.path.exists(self.loss_vector_utm_path):
            QMessageBox.warning(
                self.dialog, "Aviso", "Reprojete os vetores primeiro na aba Vectorize.")
            return

        self.loss_layer = self.ensure_fields(
            self.loss_vector_utm_path, "Loss Vector UTM")
        if self.loss_layer:
            QgsProject.instance().addMapLayer(self.loss_layer)
            self.log_message(
                "Loss Vector UTM loaded via load_loss_vector (compatibility).")

    def next_to_export(self):
        """Avança para a aba Export & Finish (compatibilidade com botões UI antigos).

        Este método foi adicionado explicitamente dentro da classe para garantir
        que `self.next_to_export` exista quando sinais tentarem conectar-se a ele.
        """
        try:
            current_index = self.dialog.tabWidget.currentIndex()
            next_index = current_index + 1
            # Habilita o próximo tab e avança
            self.dialog.tabWidget.setTabEnabled(next_index, True)
            self.dialog.tabWidget.setCurrentIndex(next_index)
            self.log_message(
                f"➡️ Advanced from tab {current_index} to {next_index} (Export & Finish). Buttons now enabled.")
        except Exception as e:
            self.log_message(
                f"Error advancing to Export & Finish tab: {str(e)}")
            try:
                QMessageBox.warning(self.dialog, "Error",
                                    f"Error advancing: {str(e)}")
            except Exception:
                # In case dialog is not available, just log
                pass

    def calculate_and_display_metrics(self):
        try:
            if not (hasattr(self, 'gain_vector_utm_path') and self.gain_vector_utm_path or hasattr(self, 'loss_vector_utm_path') and self.loss_vector_utm_path):
                QMessageBox.warning(
                    self.dialog, "Warning", "Gain/Loss vectors UTM have not been generated yet.")
                return

            # Sempre computa métricas nos layers (se existirem ou recriados)
            if hasattr(self, 'gain_layer') and self.gain_layer:
                self.gain_layer = self.compute_metrics_on_layer(
                    self.gain_layer, "Gain Vectors (with Metrics)")
            else:
                self.gain_layer = self.ensure_fields(
                    self.gain_vector_utm_path, "Gain Vectors (with Metrics)")

            if hasattr(self, 'loss_layer') and self.loss_layer:
                self.loss_layer = self.compute_metrics_on_layer(
                    self.loss_layer, "Loss Vectors (with Metrics)")
            else:
                self.loss_layer = self.ensure_fields(
                    self.loss_vector_utm_path, "Loss Vectors (with Metrics)")

            if self.gain_layer:
                self._load_vector_to_project(
                    self.gain_layer.source(), "Gain Vectors (with Metrics)")
            if self.loss_layer:
                self._load_vector_to_project(
                    self.loss_layer.source(), "Loss Vectors (with Metrics)")

            # Config sliders com ranges dinâmicos (agora como método da classe)
            self.init_dynamic_sliders(self.gain_layer, self.loss_layer)

            QMessageBox.information(
                self.dialog, "Metrics", "Metrics computed and layers updated. Adjust filters with sliders.")
        except Exception as e:
            self.log_message(f"Error computing metrics: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error computing metrics: {str(e)}")

    def init_dynamic_sliders(self, gain_layer, loss_layer):
        """Ajusta ranges dos sliders/spins baseado em stats reais das layers."""
        if not gain_layer:
            self.log_message(
                "No Gain layer for dynamic ranges — using defaults.")
            return

        # Campos a checar (pra cada um: min/max das features válidas)
        metrics_fields = ['area', 'perimeter', 'elongation', 'rectang']

        for field in metrics_fields:
            # Pega stats do Gain (prioridade, pra mais features)
            idx = gain_layer.fields().indexFromName(field)
            valid_features = [
                f for f in gain_layer.getFeatures() if f['is_valid'] == 1]
            values = [f[idx] for f in valid_features if f[idx] is not None]

            # Fallback pro Loss se Gain vazio
            if not values and loss_layer:
                idx_loss = loss_layer.fields().indexFromName(field)
                valid_features_loss = [
                    f for f in loss_layer.getFeatures() if f['is_valid'] == 1]
                values = [f[idx_loss]
                          for f in valid_features_loss if f[idx_loss] is not None]

            if values:
                min_val, max_val = min(values), max(values)
                self.log_message(
                    f"Dynamic range for {field}: {min_val} to {max_val}")

                # Ajusta slider (0 a algo amplo, tipo 10x o max pra
                # Folga de 50% pra não cortar
                slider_max = int(max_val * 1.5) if max_val > 0 else 1000
                spin_max = max_val * 2  # Spin mais generoso

                # Ajusta widgets (se existirem no dialog)
                if hasattr(self.dialog, f'slider{field.capitalize()}'):
                    slider_widget = getattr(
                        self.dialog, f'slider{field.capitalize()}')
                    slider_widget.setRange(0, slider_max)
                    slider_widget.setValue(0)  # Reset pra mínimo inicial
                if hasattr(self.dialog, f'spin{field.capitalize()}'):
                    spin_widget = getattr(
                        self.dialog, f'spin{field.capitalize()}')
                    spin_widget.setRange(0, spin_max)
                    spin_widget.setValue(0)

                # Mesma coisa pro preview? Não aqui — faz no open_filtered_preview se quiser sliders locais dinâmicos
            else:
                self.log_message(
                    f"No valid values for {field} — keeping default range.")

        # Valores iniciais lenientes pros spins (pra ver algo na seleção logo de cara)
        if hasattr(self.dialog, 'spinArea'):
            self.dialog.spinArea.setValue(0.1)  # Quase zero pra área
        if hasattr(self.dialog, 'spinRectangularity'):
            self.dialog.spinRectangularity.setValue(
                0.01)  # Leniente pra retangularidade

    def compute_metrics_on_layer(self, layer, layer_name):
        """Computa métricas para TODOS os polígonos, marcando inválidos."""
        if not layer or not layer.isValid():
            raise Exception(f"Invalid layer: {layer_name}")

        # O _ensure_temp_dir e a exportação para temp_dir são chamados em next_to_metrics.
        # Não é necessário garantir o diretório aqui.

        # Corrige geometrias e converte para singlepart (mantém)
        fixed_path = os.path.join(
            self.temp_dir, f"fixed_{layer_name.lower().replace(' ', '_')}.shp")
        try:
            processing.run("qgis:fixgeometries", {'INPUT': layer, 'OUTPUT': fixed_path})
        except Exception as e:
            self.log_message(f"Processing error running fixgeometries for {layer_name}: {e}")
            raise Exception(f"Failed to run fixgeometries for {layer_name}: {e}")

        if not os.path.exists(fixed_path):
            raise Exception(f"fixgeometries did not produce output file: {fixed_path}. Check temp dir and permissions.")

        fixed_layer = QgsVectorLayer(fixed_path, "Fixed Layer", "ogr")
        if not fixed_layer.isValid():
            raise Exception(f"Fixed geometries output invalid for {layer_name}: {fixed_path}. Check drivers and file integrity.")

        single_path = os.path.join(
            self.temp_dir, f"single_{layer_name.lower().replace(' ', '_')}.shp")
        try:
            processing.run("qgis:multiparttosingleparts", {'INPUT': fixed_layer, 'OUTPUT': single_path})
        except Exception as e:
            self.log_message(f"Processing error running multiparttosingleparts for {layer_name}: {e}")
            raise Exception(f"Failed to run multiparttosingleparts for {layer_name}: {e}")

        if not os.path.exists(single_path):
            raise Exception(f"multiparttosingleparts did not produce output file: {single_path}. Check temp dir and permissions.")

        layer = QgsVectorLayer(single_path, layer_name, "ogr")
        if not layer.isValid():
            raise Exception(f"Singlepart output invalid for {layer_name}: {single_path}. Check drivers and file integrity.")

        self.log_message(
            f"Geometries fixed and converted to singlepart for {layer_name}")

        if layer.isEditable():
            layer.rollBack()

        if not layer.startEditing():
            raise Exception(f"Could not start editing on {layer_name}")

        prov = layer.dataProvider()
        existing = {f.name().lower() for f in layer.fields()}

        needed = []
        if 'area' not in existing:
            needed.append(QgsField('area', QVariant.Double))
        if 'perimeter' not in existing:
            needed.append(QgsField('perimeter', QVariant.Double))
        if 'elongation' not in existing:
            needed.append(QgsField('elongation', QVariant.Double))
        if 'rectang' not in existing:
            needed.append(QgsField('rectang', QVariant.Double))
        if 'is_valid' not in existing:  # Novo campo para marcar válidos
            needed.append(QgsField('is_valid', QVariant.Int))

        if needed:
            if not prov.addAttributes(needed):
                raise Exception(f"Failed to add attributes to {layer_name}")
            layer.updateFields()
            self.log_message(
                f"Added fields to {layer_name}: {', '.join([f.name() for f in needed])}")

        area_idx = layer.fields().indexOf('area')
        per_idx = layer.fields().indexOf('perimeter')
        el_idx = layer.fields().indexOf('elongation')
        rect_idx = layer.fields().indexOf('rectang')
        valid_idx = layer.fields().indexOf('is_valid')
        val_idx = layer.fields().indexOf('val') if 'val' in existing else -1

        changes = {}
        total_features = layer.featureCount()
        valid_count = 0
        invalid_count = 0
        self.log_message(
            f"Processing {total_features} features in {layer_name}")

        for f in layer.getFeatures():
            fid = f.id()
            geom = f.geometry()
            if not geom or geom.isEmpty() or not geom.isGeosValid():
                self.log_message(f"Feature {fid} skipped: geometry invalid")
                changes[fid] = {valid_idx: 0}
                invalid_count += 1
                continue

            # Não pula por val: Calcula para todos, mas valida depois
            area = geom.area()
            perimeter = geom.length()

            # Cálculo de OBB com fallback para bug (rectang >1)
            obb = geom.orientedMinimumBoundingBox()
            elongation = 0
            rectangularity = 0
            use_fallback = False

            if isinstance(obb, tuple) and len(obb) == 5:
                rect_geom, angle, width, height, rect_area = obb
                if width > 0 and height > 0:
                    elongation = max(width, height) / min(width, height)
                if rect_area > 0:
                    rectangularity = area / rect_area
                    if rectangularity > 1.0:  # Bug detectado: usa convexHull como fallback
                        self.log_message(
                            f"Feature {fid}: OBB bug detected (rectang={rectangularity}>1), using convexHull fallback")
                        convex = geom.convexHull()
                        bbox = convex.boundingBox()
                        rect_area_fallback = bbox.width() * bbox.height()
                        rectangularity = area / rect_area_fallback if rect_area_fallback > 0 else 0
                        use_fallback = True
                else:
                    rectangularity = 0
            else:
                self.log_message(
                    f"Feature {fid}: Invalid OBB format, skipping metrics")
                changes[fid] = {valid_idx: 0}
                invalid_count += 1
                continue

            # Validação suave: Marca como inválido se ruído extremo, mas calcula métricas
            is_valid = 1
            # Critérios ajustados (mais lenientes)
            if area < 0.5 or elongation > 100 or rectangularity < 0.1:
                is_valid = 0
                invalid_count += 1
                self.log_message(
                    f"Feature {fid} marked invalid: area={area}, elong={elongation}, rect={rectangularity}")
            else:
                valid_count += 1

            changes[fid] = {
                area_idx: area,
                per_idx: perimeter,
                el_idx: elongation,
                rect_idx: rectangularity,
                valid_idx: is_valid
            }

        if changes:
            if not prov.changeAttributeValues(changes):
                raise Exception(f"Failed to update attributes in {layer_name}")
            self.log_message(
                f"Updated metrics for {total_features} features in {layer_name}: {valid_count} valid, {invalid_count} invalid/ruído")

        if not layer.commitChanges():
            raise Exception(f"Failed to commit changes in {layer_name}")

        return layer

    def _remove_background_features(self, vector_path, field_name, value_to_remove):
        """Remove feições de um shapefile onde o campo especificado tem o valor especificado."""
        try:
            layer = QgsVectorLayer(vector_path, os.path.basename(vector_path), "ogr")
            if not layer.isValid():
                self.log_message(f"Falha ao carregar layer para remoção de background: {vector_path}")
                return

            if not layer.startEditing():
                self.log_message(f"Falha ao iniciar edição para remoção de background: {vector_path}")
                return

            ids_to_delete = []
            for feature in layer.getFeatures():
                if feature[field_name] == value_to_remove:
                    ids_to_delete.append(feature.id())

            if ids_to_delete:
                layer.deleteFeatures(ids_to_delete)
                layer.commitChanges()
                self.log_message(f"Removidas {len(ids_to_delete)} feições de background (valor {value_to_remove} no campo '{field_name}') de {os.path.basename(vector_path)}")
            else:
                layer.rollBack()
                self.log_message(f"Nenhuma feição de background encontrada para remoção em {os.path.basename(vector_path)}")

        except Exception as e:
            self.log_message(f"Erro ao remover feições de background em {vector_path}: {str(e)}")
            try:
                layer.rollBack()
            except Exception:
                pass

    def filter_vectors_by_metrics(self):
        try:
            # Prioriza SpinBox para precisão; fallback para slider se não existir
            min_area = self.dialog.spinArea.value() if hasattr(
                self.dialog, 'spinArea') else self.dialog.sliderArea.value()
            min_per = self.dialog.spinPerimeter.value() if hasattr(
                self.dialog, 'spinPerimeter') else self.dialog.sliderPerimeter.value()
            max_el = self.dialog.spinElongation.value() if hasattr(
                self.dialog, 'spinElongation') else self.dialog.sliderElongation.value() / 10.0
            min_rect = self.dialog.spinRectangularity.value() if hasattr(
                self.dialog, 'spinRectangularity') else self.dialog.sliderRectangularity.value() / 100.0

            # Atualiza labels informativos (se existirem)
            if hasattr(self.dialog, 'labelMinArea'):
                self.dialog.labelMinArea.setText(
                    f"Min area: {self.dialog.sliderArea.value():,}")
            if hasattr(self.dialog, 'labelMinPerimeter'):
                self.dialog.labelMinPerimeter.setText(
                    f"Min perimeter: {self.dialog.sliderPerimeter.value():,}")
            if hasattr(self.dialog, 'labelMaxElongation'):
                self.dialog.labelMaxElongation.setText(
                    f"Max elongation: {self.dialog.sliderElongation.value()/10:.1f}")
            if hasattr(self.dialog, 'labelMinRectangularity'):
                self.dialog.labelMinRectangularity.setText(
                    f"Min rectang: {self.dialog.sliderRectangularity.value()/100:.2f}")

            expression_base = (
                f'"area" >= {min_area} AND '
                f'"perimeter" >= {min_per} AND '
                f'"elongation" <= {max_el} AND '
                f'"rectang" >= {min_rect} AND "is_valid" = 1'
            )
            self.log_message(
                f"Applying selection expression: {expression_base}")

            gain_layers = QgsProject.instance().mapLayersByName("Gain Vectors (with Metrics)")
            loss_layers = QgsProject.instance().mapLayersByName("Loss Vectors (with Metrics)")

            if not gain_layers and not loss_layers:
                self.log_message("No metric layers found to filter.")
                QMessageBox.warning(self.dialog, "Warning",
                                    "No metric layers available (Gain/Loss). Run 'Calculate Metrics and Filter' first.")
                return

            def _total_features_safe(layer):
                try:
                    cnt = layer.featureCount()
                    if cnt is None or cnt < 0:
                        # Some providers return -1/-2 for unknown counts; iterate instead
                        cnt = sum(1 for _ in layer.getFeatures())
                    return cnt
                except Exception:
                    try:
                        return sum(1 for _ in layer.getFeatures())
                    except Exception:
                        return 0

            # Para Gain
            if gain_layers and len(gain_layers) > 0:
                gain_layer = gain_layers[0]
                if not gain_layer or not gain_layer.isValid():
                    self.log_message("⚠️ Gain layer is invalid or could not be loaded.")
                else:
                    total = _total_features_safe(gain_layer)
                    self.log_message(f"📊 Layer diagnostics: Total features = {total}")
                    if total == 0:
                        self.log_message("⚠️ Gain layer has no features - skipping gain filter.")
                    else:
                        expression = expression_base + ' AND "val" = 255'
                        gain_layer.removeSelection()
                        gain_layer.selectByExpression(expression)
                        self.log_message(
                            f"Test expression: {expression} — Applied")
                        after_select = gain_layer.selectedFeatureCount()
                        self.log_message(f"Selected: {after_select} features")
                        if after_select == 0:
                            # Fallback: selecione só válidas
                            gain_layer.selectByExpression(
                                '"is_valid" = 1 AND "val" = 255')
                            self.log_message("Fallback: All valid selected")
                        try:
                            self.iface.layerTreeView().refreshLayerSymbology(gain_layer.id())
                        except Exception:
                            pass

            # Para Loss (repete o padrão)
            if loss_layers and len(loss_layers) > 0:
                loss_layer = loss_layers[0]
                if not loss_layer or not loss_layer.isValid():
                    self.log_message("⚠️ Loss layer is invalid or could not be loaded.")
                else:
                    total = _total_features_safe(loss_layer)
                    self.log_message(f"📊 Layer diagnostics: Total features = {total}")
                    if total == 0:
                        self.log_message("⚠️ Loss layer has no features - skipping loss filter.")
                    else:
                        expression = expression_base + ' AND "val" = 255'
                        loss_layer.removeSelection()
                        loss_layer.selectByExpression(expression)
                        self.log_message(
                            f"Test expression: {expression} — Applied")
                        after_select = loss_layer.selectedFeatureCount()
                        self.log_message(f"Selected: {after_select} features")
                        if after_select == 0:
                            # Fallback: selecione só válidas
                            loss_layer.selectByExpression(
                                '"is_valid" = 1 AND "val" = 255')
                            self.log_message("Fallback: All valid selected")
                        try:
                            self.iface.layerTreeView().refreshLayerSymbology(loss_layer.id())
                        except Exception:
                            pass

            self.log_message(
                f"Filter applied: area>={min_area}, per>={min_per}, elong<={max_el}, rect>={min_rect}")

        except Exception as e:
            self.log_message(f"Error filtering by metrics: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error filtering by metrics: {e}")

    def apply_filter_and_show_table(self):
        """Aplica filtro e abre tabela de atributos (chamado pelo botão Apply)."""
        self.filter_vectors_by_metrics()  # Roda filtro (atualiza seleção sem abrir tabela)

        # Abre tabelas só se features selecionadas (uma por layer)
        gain_layers = QgsProject.instance().mapLayersByName("Gain Vectors (with Metrics)")
        loss_layers = QgsProject.instance().mapLayersByName("Loss Vectors (with Metrics)")

        if gain_layers and gain_layers[0].selectedFeatureCount() > 0:
            self.iface.showAttributeTable(gain_layers[0])
            self.log_message("Applied filter and opened Gain attribute table")
        if loss_layers and loss_layers[0].selectedFeatureCount() > 0:
            self.iface.showAttributeTable(loss_layers[0])
            self.log_message("Applied filter and opened Loss attribute table")

        if not (gain_layers or loss_layers) or (gain_layers[0].selectedFeatureCount() == 0 and loss_layers[0].selectedFeatureCount() == 0):
            QMessageBox.information(
                self.dialog, "Info", "Filter applied, but no features match. Adjust values and try again.")

    def open_filtered_preview(self):
        """Abre janela auxiliar de filtro interativo de métricas (Área, Perímetro, Elongação, Retangularidade)
        aplicada sobre as camadas 'Gain Vectors (with Metrics)' e 'Loss Vectors (with Metrics)'.
        """
        self.log_message(
            "🔍 Button clicked: Starting open_filtered_preview...")  # ← NOVO: Confirma clique

        # Garantir que o diretório temp exista — previne erros como 'is not a directory'
        try:
            if not hasattr(self, 'temp_dir') or not self.temp_dir:
                self.temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
            os.makedirs(self.temp_dir, exist_ok=True)
            self.log_message(f"Using temp dir: {self.temp_dir}")
        except Exception as e:
            # Log e continua; operações que escrevem irão tratar erros explicitamente
            self.log_message(f"Could not ensure temp dir: {e}")

        gain_layers = QgsProject.instance().mapLayersByName("Gain Vectors (with Metrics)")
        loss_layers = QgsProject.instance().mapLayersByName("Loss Vectors (with Metrics)")
        self.log_message(
            f"Found {len(gain_layers)} gain layers and {len(loss_layers)} loss layers.")

        if not (gain_layers or loss_layers):
            self.log_message("No metric layers found - aborting preview.")
            QMessageBox.warning(
                self.dialog, "Warning", "No metric layers available (Gain/Loss). Run 'Calculate Metrics and Filter' first.")
            return

        gain_layer = gain_layers[0] if gain_layers else None
        loss_layer = loss_layers[0] if loss_layers else None

        # Ativa modo de edição automático nas layers (como no UTM)
        if gain_layer and gain_layer.isValid():
            gain_layer.startEditing()
            self.log_message("✅ Gain layer entered edit mode.")
        if loss_layer and loss_layer.isValid():
            loss_layer.startEditing()
            self.log_message("✅ Loss layer entered edit mode.")

        # ← NOVO: Antes de criar dlg
        self.log_message("📦 Creating main dialog...")

        # === Cria janela principal
        # CORREÇÃO 2: Armazenar o diálogo como atributo para evitar que seja destruído prematuramente
        if hasattr(self, '_preview_dialog') and self._preview_dialog is not None:
            try:
                self._preview_dialog.close()
            except:
                pass
        self._preview_dialog = QDialog(self.dialog)
        dlg = self._preview_dialog
        dlg.setWindowTitle("Metrics Filter Preview")
        dlg.resize(1000, 900)
        main_layout = QVBoxLayout(dlg)

        # ← NOVO: Confirma criação
        self.log_message("✅ Dialog created and resized.")

        # ===============================
        # BLOCO GAIN
        # ===============================
        gain_box = QGroupBox("Gain Layer Preview")
        gain_layout = QVBoxLayout(gain_box)

        # Canvas Gain
        gain_canvas = QgsMapCanvas()
        gain_canvas.setCanvasColor(Qt.white)
        gain_canvas.enableAntiAliasing(True)
        gain_layout.addWidget(gain_canvas)

        # ---- Sliders / Spins ----
        def metric_slider(label, minv, maxv, step, scale=1.0, decimals=2, unit="", is_min=True):
            """
            Cria um controle horizontal composto por QLabel + QSlider + QDoubleSpinBox,
            permitindo valores decimais de forma sincronizada.
            + Novo: Label com min/max e unidade.
            """
            box = QHBoxLayout()
            lbl = QLabel(label)

            # ← NOVO: Label com min/max e unidade
            range_lbl = QLabel(f"[{minv} - {maxv}] {unit}")
            # Pequeno e cinza pra não poluir
            range_lbl.setStyleSheet("QLabel { color: gray; font-size: 9px; }")

            # Slider sempre em inteiros (escala aplicada)
            sld = QSlider(Qt.Horizontal)
            sld.setRange(int(minv * scale), int(maxv * scale))
            sld.setSingleStep(int(step * scale))
            sld.setValue(int(minv * scale))

            # SpinBox com decimais
            spn = QDoubleSpinBox()
            spn.setDecimals(decimals)
            spn.setRange(minv, maxv)
            spn.setSingleStep(step)
            spn.setValue(minv)

            box.addWidget(lbl)
            box.addWidget(range_lbl)  # ← NOVO: Adiciona o range label
            box.addWidget(sld)
            box.addWidget(spn)

            # NOTE: avoid automatic bidirectional connections here to prevent
            # recursive signal loops. Connections will be created explicitly
            # after the controls are returned, with proper signal blocking.

            return box, sld, spn

        gain_area_box, slider_area_g, spin_area_g = metric_slider(
            "Min Area:", 0, 200, 1)
        gain_per_box, slider_per_g, spin_per_g = metric_slider(
            "Min Perimeter:", 0, 150, 1)
        gain_elo_box, slider_el_g, spin_el_g = metric_slider(
            "Max Elongation:", 0, 500, 5, decimals=1, scale=10.0)
        gain_rec_box, slider_rec_g, spin_rec_g = metric_slider(
            "Min Rectangularity:", 0, 100, 1, decimals=2, scale=100.0)

        for box in [gain_area_box, gain_per_box, gain_elo_box, gain_rec_box]:
            gain_layout.addLayout(box)

        # ---- Sincroniza sliders/spins ----
        # CORREÇÃO: Usar a precisão do QDoubleSpinBox para o slider de área
        # O slider deve ser um QDoubleSpinBox ou usar um fator de escala para o QSlider
        # Como o slider é um QSlider (int), vamos usar um fator de escala (100)
        # para simular a precisão de duas casas decimais no spin box.
        # O QSlider deve ser reconfigurado para ter um range maior.
        # No entanto, a função metric_slider já cria o QSlider.
        # Vamos assumir que o QSlider é um QSlider (int) e o spin é QDoubleSpinBox.
        # A conversão de volta para int no spin_area_g.valueChanged é o problema.
        # A solução é usar o QDoubleSpinBox como a fonte de verdade e o QSlider como um visualizador/ajustador grosseiro.
        # Ou, melhor, reconfigurar o QSlider para usar um fator de escala.
        
        # Vamos reconfigurar o QSlider para usar um fator de escala de 100 (2 casas decimais)
        slider_area_g.setRange(0, 20000) # 0.00 a 200.00
        slider_area_g.setValue(int(spin_area_g.value() * 100))
        
        def update_spin_area_g(val):
            try:
                spin_area_g.blockSignals(True)
                spin_area_g.setValue(val / 100.0)
            finally:
                spin_area_g.blockSignals(False)

        def update_slider_area_g(val):
            try:
                slider_area_g.blockSignals(True)
                slider_area_g.setValue(int(val * 100))
            finally:
                slider_area_g.blockSignals(False)
            
        slider_area_g.valueChanged.connect(update_spin_area_g)
        spin_area_g.valueChanged.connect(update_slider_area_g)

        # CORREÇÃO: Usar a precisão do QDoubleSpinBox para o slider de perímetro
        slider_per_g.setRange(0, 15000) # 0.00 a 150.00
        slider_per_g.setValue(int(spin_per_g.value() * 100))
        
        def update_spin_per_g(val):
            try:
                spin_per_g.blockSignals(True)
                spin_per_g.setValue(val / 100.0)
            finally:
                spin_per_g.blockSignals(False)

        def update_slider_per_g(val):
            try:
                slider_per_g.blockSignals(True)
                slider_per_g.setValue(int(val * 100))
            finally:
                slider_per_g.blockSignals(False)
            
        slider_per_g.valueChanged.connect(update_spin_per_g)
        spin_per_g.valueChanged.connect(update_slider_per_g)

        # Elongation (Alargamento)
        slider_el_g.setRange(0, 5000) # 0.0 a 500.0
        slider_el_g.setValue(int(spin_el_g.value() * 10))
        
        def update_spin_el_g(val):
            try:
                spin_el_g.blockSignals(True)
                spin_el_g.setValue(val / 10.0)
            finally:
                spin_el_g.blockSignals(False)

        def update_slider_el_g(val):
            try:
                slider_el_g.blockSignals(True)
                slider_el_g.setValue(int(val * 10))
            finally:
                slider_el_g.blockSignals(False)
            
        slider_el_g.valueChanged.connect(update_spin_el_g)
        spin_el_g.valueChanged.connect(update_slider_el_g)

        # Rectangularity (Retangularidade)
        slider_rec_g.setRange(0, 100) # 0.00 a 1.00 (0 a 100 no slider)
        slider_rec_g.setValue(int(spin_rec_g.value() * 100))
        
        def update_spin_rec_g(val):
            try:
                spin_rec_g.blockSignals(True)
                spin_rec_g.setValue(val / 100.0)
            finally:
                spin_rec_g.blockSignals(False)

        def update_slider_rec_g(val):
            try:
                slider_rec_g.blockSignals(True)
                slider_rec_g.setValue(int(val * 100))
            finally:
                slider_rec_g.blockSignals(False)
            
        slider_rec_g.valueChanged.connect(update_spin_rec_g)
        spin_rec_g.valueChanged.connect(update_slider_rec_g)

        # ---- Botões ----
        gain_btn_apply = QPushButton("Apply Filter (Gain)")
        gain_btn_export = QPushButton("Export Gain Selection")
        gain_layout.addWidget(gain_btn_apply)
        gain_layout.addWidget(gain_btn_export)

        main_layout.addWidget(gain_box)

        # ===============================
        # BLOCO LOSS
        # ===============================
        loss_box = QGroupBox("Loss Layer Preview")
        loss_layout = QVBoxLayout(loss_box)

        loss_canvas = QgsMapCanvas()
        loss_canvas.setCanvasColor(Qt.white)
        loss_canvas.enableAntiAliasing(True)
        loss_layout.addWidget(loss_canvas)

        loss_area_box, slider_area_l, spin_area_l = metric_slider(
            "Min Area:", 0, 200, 1)
        loss_per_box, slider_per_l, spin_per_l = metric_slider(
            "Min Perimeter:", 0, 150, 1)
        loss_elo_box, slider_el_l, spin_el_l = metric_slider(
            "Max Elongation:", 0, 500, 5, decimals=1, scale=10.0)
        # CORREÇÃO 2: O slider de rectangularity estava usando o spin de elongation (slider_el_l)
        loss_rec_box, slider_rec_l, spin_rec_l = metric_slider(
            "Min Rectangularity:", 0, 1.0, 0.01, decimals=2, scale=100.0)

        for box in [loss_area_box, loss_per_box, loss_elo_box, loss_rec_box]:
            loss_layout.addLayout(box)

        # CORREÇÃO: Usar a precisão do QDoubleSpinBox para o slider de área (Loss)
        slider_area_l.setRange(0, 20000) # 0.00 a 200.00
        slider_area_l.setValue(int(spin_area_l.value() * 100))
        
        def update_spin_area_l(val):
            try:
                spin_area_l.blockSignals(True)
                spin_area_l.setValue(val / 100.0)
            finally:
                spin_area_l.blockSignals(False)

        def update_slider_area_l(val):
            try:
                slider_area_l.blockSignals(True)
                slider_area_l.setValue(int(val * 100))
            finally:
                slider_area_l.blockSignals(False)
            
        slider_area_l.valueChanged.connect(update_spin_area_l)
        spin_area_l.valueChanged.connect(update_slider_area_l)

        # CORREÇÃO: Usar a precisão do QDoubleSpinBox para o slider de perímetro (Loss)
        slider_per_l.setRange(0, 15000) # 0.00 a 150.00
        slider_per_l.setValue(int(spin_per_l.value() * 100))
        
        def update_spin_per_l(val):
            try:
                spin_per_l.blockSignals(True)
                spin_per_l.setValue(val / 100.0)
            finally:
                spin_per_l.blockSignals(False)

        def update_slider_per_l(val):
            try:
                slider_per_l.blockSignals(True)
                slider_per_l.setValue(int(val * 100))
            finally:
                slider_per_l.blockSignals(False)
            
        slider_per_l.valueChanged.connect(update_spin_per_l)
        spin_per_l.valueChanged.connect(update_slider_per_l)

        # Elongation (Alargamento) (Loss)
        slider_el_l.setRange(0, 5000) # 0.0 a 500.0
        slider_el_l.setValue(int(spin_el_l.value() * 10))
        
        def update_spin_el_l(val):
            try:
                spin_el_l.blockSignals(True)
                spin_el_l.setValue(val / 10.0)
            finally:
                spin_el_l.blockSignals(False)

        def update_slider_el_l(val):
            try:
                slider_el_l.blockSignals(True)
                slider_el_l.setValue(int(val * 10))
            finally:
                slider_el_l.blockSignals(False)
            
        slider_el_l.valueChanged.connect(update_spin_el_l)
        spin_el_l.valueChanged.connect(update_slider_el_l)

        # Rectangularity (Retangularidade) (Loss)
        slider_rec_l.setRange(0, 100) # 0.00 a 1.00 (0 a 100 no slider)
        slider_rec_l.setValue(int(spin_rec_l.value() * 100))
        
        def update_spin_rec_l(val):
            try:
                spin_rec_l.blockSignals(True)
                spin_rec_l.setValue(val / 100.0)
            finally:
                spin_rec_l.blockSignals(False)

        def update_slider_rec_l(val):
            try:
                slider_rec_l.blockSignals(True)
                slider_rec_l.setValue(int(val * 100))
            finally:
                slider_rec_l.blockSignals(False)
            
        slider_rec_l.valueChanged.connect(update_spin_rec_l)
        spin_rec_l.valueChanged.connect(update_slider_rec_l)

        loss_btn_apply = QPushButton("Apply Filter (Loss)")
        loss_btn_export = QPushButton("Export Loss Selection")
        loss_layout.addWidget(loss_btn_apply)
        loss_layout.addWidget(loss_btn_export)

        main_layout.addWidget(loss_box)

        # ===============================
        # FUNÇÕES DE AÇÃO
        # ===============================
        def apply_filter(layer, canvas, is_gain=True):
            """Aplica filtros e atualiza seleção"""
            # CORREÇÃO 2: Usar self._preview_dialog em vez de dlg
            dlg = self._preview_dialog
            
            if not layer or not layer.isValid():
                QMessageBox.warning(dlg, "Warning", "Layer invalid.")
                return

            # Verifica se os campos necessários existem
            required_fields = ['area', 'perimeter',
                               'elongation', 'rectang', 'is_valid', 'val']
            existing_fields = [f.name() for f in layer.fields()]
            missing_fields = [
                f for f in required_fields if f not in existing_fields]
            if missing_fields:
                # Limita pra não flood
                self.log_message(
                    f"❌ Missing fields in layer: {missing_fields}. Available: {existing_fields[:5]}...")
                QMessageBox.warning(
                    dlg, "Warning", f"Missing fields: {', '.join(missing_fields)}. Run 'Calculate Metrics' first.")
                return

            # ← CORRIGIDO: Log de diagnóstico - total de features e amostra de atributos
            total_feats = layer.featureCount()
            self.log_message(
                f"📊 Layer diagnostics: Total features = {total_feats}")
            if total_feats > 0:
                # Pega as primeiras 3 features iterando (sem slicing no iterator)
                sample_feats = []
                it = layer.getFeatures()
                for i in range(3):
                    f = next(it, None)
                    if f:
                        sample_feats.append(f)
                    else:
                        break
                for i, feat in enumerate(sample_feats):
                    attrs = {f.name(): feat[f.name()] for f in layer.fields(
                    ) if f.name() in required_fields}
                    self.log_message(f"   Sample feature {i+1}: {attrs}")
            else:
                self.log_message("⚠️ Layer has NO features at all!")
                QMessageBox.warning(
                    dlg, "Warning", "Layer has no features. Check vectorization step.")
                return

            # ← NOVO: Teste simples sem métricas - só is_valid e val
            val_condition = 255
            simple_expr = f'"is_valid" = 1 AND "val" = {val_condition}'
            layer.selectByExpression(simple_expr)
            simple_sel = layer.selectedFeatureCount()
            self.log_message(f"🔍 Simple test (is_valid=1 AND val={val_condition}): {simple_sel} selected")
            layer.removeSelection()  # Limpa pra filtro completo

            try:
                # lê valores conforme tipo
                min_a = slider_area_g.value() if is_gain else slider_area_l.value()
                min_p = slider_per_g.value() if is_gain else slider_per_l.value()
                max_e = (slider_el_g.value()
                         if is_gain else slider_el_l.value()) / 10.0
                min_r = (slider_rec_g.value()
                         if is_gain else slider_rec_l.value()) / 100.0
                # Both gain and loss polygons use val==255 in polygonized outputs
                val_condition = 255

                # ← MUDANÇA: Expressão menos rígida - usa OR para condições opcionais se sliders em default (0/min)
                # Se todos sliders em min/default, ignora métricas e usa só is_valid + val
                # Defaults corrigidos (Max Elo=500/10=50)
                if min_a == 0 and min_p == 0 and max_e == 50.0 and min_r == 0.0:
                    expression = f'"is_valid" = 1 AND "val" = {val_condition}'
                    self.log_message(
                        "💡 Using relaxed filter (all valid + val match, ignoring metrics)")
                else:
                    # AND normal, mas com OR interno pra não travar (ex.: (area OR perimeter) mas mantendo essencial)
                    # Pra simplificar: Agrupa métricas em OR opcional, mas mantém is_valid/val como AND
                    metrics_part = (
                        f'("area" >= {min_a} OR "perimeter" >= {min_p} OR "elongation" <= {max_e} OR "rectang" >= {min_r})'
                    )
                    expression = f'{metrics_part} AND "is_valid" = 1 AND "val" = {val_condition}'
                    self.log_message(
                        "💡 Using OR-based metrics filter (less rigid)")

                # ← NOVO: Log da expressão exata
                self.log_message(f"🔍 Applying expression: {expression}")

                layer.removeSelection()
                layer.selectByExpression(expression)
                sel = layer.selectedFeatureCount()
                self.log_message(
                    f"[{'Gain' if is_gain else 'Loss'}] Filter applied → {sel} selected features")

                if sel > 0:
                    canvas.setLayers([layer])
                    canvas.zoomToSelected()
                    canvas.refresh()
                    self.log_message(
                        f"✅ Zoomed to {sel} selected features on canvas.")
                    # Força destaque visual (opcional, mas garante)
                    # Amarelo semi-transparente
                    canvas.setSelectionColor(QColor(255, 255, 0, 200))
                else:
                    self.log_message(
                        "⚠️ No features matched the filter. Try loosening sliders.")
                    QMessageBox.information(
                        dlg, "Info", "No features selected. Adjust sliders and try again.")
            except Exception as e:
                self.log_message(f"❌ Error applying filter: {e}")
                import traceback
                # ← NOVO: Stack trace pra debug
                self.log_message(traceback.format_exc())

        # ← CORRIGIDO: Movido para fora de apply_filter (indentação corrigida)
        def export_selection(layer, out_path):
            if not layer or not layer.selectedFeatureCount():
                QMessageBox.warning(
                    dlg, "Warning", "No features selected to export.")
                return
            try:
                # Salva o shapefile filtrado
                QgsVectorFileWriter.writeAsVectorFormat(
                    layer, out_path, "UTF-8", driverName="ESRI Shapefile", onlySelected=True)
                self.log_message(f"Exported selection to {out_path}")
                QMessageBox.information(
                    dlg, "Export", f"Selection exported:\n{out_path}")

                # ← NOVO: Carrega a layer no projeto QGIS automaticamente
                layer_name = "Filtered Gain" if "gain" in out_path.lower() else "Filtered Loss"
                new_layer = QgsVectorLayer(out_path, layer_name, "ogr")
                if new_layer.isValid():
                    QgsProject.instance().addMapLayer(new_layer)
                    self.log_message(
                        f"✅ Loaded '{layer_name}' layer in QGIS project ({layer.selectedFeatureCount()} features).")
                else:
                    # QgsVectorLayer.error() may vary by QGIS version; try to log useful info
                    try:
                        err = new_layer.error().summary()
                    except Exception:
                        err = "(no error summary available)"
                    self.log_message(
                        f"⚠️ Failed to load exported layer: {err}")
                    QMessageBox.warning(
                        dlg, "Warning", f"Exported but failed to load layer. Check log.")

            except Exception as e:
                QMessageBox.warning(dlg, "Error", str(e))
                self.log_message(f"Export failed: {e}")

        # === conecta ações
        # ← NOVO: Antes das conexões
        self.log_message("🔗 Connecting buttons...")
        gain_btn_apply.clicked.connect(
            lambda: apply_filter(gain_layer, gain_canvas, True))
        loss_btn_apply.clicked.connect(
            lambda: apply_filter(loss_layer, loss_canvas, False))
        gain_btn_export.clicked.connect(lambda: export_selection(
            gain_layer, os.path.join(self.temp_dir, "gain_filtered.shp")))
        loss_btn_export.clicked.connect(lambda: export_selection(
            loss_layer, os.path.join(self.temp_dir, "loss_filtered.shp")))

        # === popula canvas inicial com segurança
        self.log_message("🖼️ Initializing canvases...")  # ← NOVO: Antes do try
        try:
            if gain_layer and gain_layer.isValid():
                gain_canvas.setLayers([gain_layer])
                gain_canvas.setExtent(gain_layer.extent())
                gain_canvas.refresh()
                self.log_message("✅ Gain canvas populated.")
            if loss_layer and loss_layer.isValid():
                loss_canvas.setLayers([loss_layer])
                loss_canvas.setExtent(loss_layer.extent())
                loss_canvas.refresh()
                self.log_message("✅ Loss canvas populated.")
        except Exception as e:
            self.log_message(f"❌ Error initializing preview canvases: {e}")

        # ← NOVO: Antes de mostrar
        self.log_message("🚀 About to exec_() dialog...")
        result = self._preview_dialog.exec_()  # ← MUDANÇA: Captura o result
        # ← NOVO: Depois de fechar
        self.log_message(
            f"🏁 Dialog closed with result: {result} (0=Reject, 1=Accept)")

        # Opcional: Salva edições nas layers ao fechar (se modificadas)
        if gain_layer:
            if gain_layer.isModified():
                gain_layer.commitChanges()
                self.log_message("💾 Gain layer changes committed.")
        if loss_layer:
            if loss_layer.isModified():
                loss_layer.commitChanges()
                self.log_message("💾 Loss layer changes committed.")

    def filter_vectors_by_metrics_local(self, gain_layer, loss_layer, min_a, min_p, max_e, min_r):
        """Filtro local pro preview dialog (sem abrir tabela)."""
        # 👉 Validação adaptada pros parâmetros (não fetch novo)
        if gain_layer is None:
            self.log_message("No Gain layer provided!")
            return
        # Cheque campos pro Gain
        fields_gain = [f.name() for f in gain_layer.fields()]
        if 'area' not in fields_gain:
            self.log_message("Campo 'area' missing in Gain layer!")
            return

        if loss_layer is None:
            self.log_message("No Loss layer provided!")
            return
        # Cheque campos pro Loss (opcional, mas bom pra consistência)
        fields_loss = [f.name() for f in loss_layer.fields()]
        if 'area' not in fields_loss:
            self.log_message("Campo 'area' missing in Loss layer!")
            return

        expression_base = f'"area" >= {min_a} AND "perimeter" >= {min_p} AND "elongation" <= {max_e} AND "rectang" >= {min_r} AND "is_valid" = 1'
        if gain_layer:
            gain_layer.removeSelection()
            gain_layer.selectByExpression(expression_base + ' AND "val" = 255')
        if loss_layer:
            loss_layer.removeSelection()
            # Loss polygons also use 255 in the raster value after polygonize/cleaning
            loss_layer.selectByExpression(expression_base + ' AND "val" = 255')

    def export_from_preview(self, gain_layer, loss_layer):
        """Export direto da seleção no preview dialog."""
        export_dir = QFileDialog.getExistingDirectory(
            self.dialog, "Export Filtered Selection")
        if export_dir:
            def _write_layer_selected(layer, out_path):
                try:
                    if not layer or layer.selectedFeatureCount() == 0:
                        return False
                    writer = QgsVectorFileWriter(
                        out_path, 'UTF-8', layer.fields(),
                        layer.wkbType(), layer.crs(), "ESRI Shapefile"
                    )
                    if writer.hasError() != QgsVectorFileWriter.NoError:
                        self.log_message(f"Failed to create writer for {out_path}: {writer.errorMessage()}")
                        return False
                    for feat in layer.selectedFeatures():
                        writer.addFeature(feat)
                    del writer
                    return True
                except Exception as e:
                    self.log_message(f"Error exporting preview layer to {out_path}: {e}")
                    return False

            exported_any = False
            if gain_layer and gain_layer.selectedFeatureCount() > 0:
                outp = os.path.join(export_dir, "preview_gain.shp")
                if _write_layer_selected(gain_layer, outp):
                    exported_any = True
                    self.log_message(f"Exported preview gain to {outp}")
            if loss_layer and loss_layer.selectedFeatureCount() > 0:
                outp = os.path.join(export_dir, "preview_loss.shp")
                if _write_layer_selected(loss_layer, outp):
                    exported_any = True
                    self.log_message(f"Exported preview loss to {outp}")

            if exported_any:
                QMessageBox.information(self.dialog, "Success", f"Exported to {export_dir}")
            else:
                QMessageBox.information(self.dialog, "Info", "No features exported from preview.")

    def apply_smoothify(self):
        """Aplica o algoritmo Smoothify nos vetores de entrada, procurando de forma inteligente
        pelo arquivo correto (processado, filtrado ou exportando na hora)."""
        try:
            # 1. Obter parâmetros da UI
            smooth_iterations = self.dialog.findChild(
                QSpinBox, "smoothIterationsSpin").value()
            segment_length = self.dialog.findChild(
                QDoubleSpinBox, "segmentLengthSpin").value()
            preserve_area = self.dialog.findChild(
                QCheckBox, "preserveAreaCheck").isChecked()
            area_tolerance = self.dialog.findChild(
                QDoubleSpinBox, "areaToleranceSpin").value() / 100.0

            # 2. Lógica inteligente para encontrar os arquivos de entrada corretos
            gain_input_path = None
            loss_input_path = None

            # Prioridade 1: Verificar se existem arquivos processados (pós-simplify/orthogonalize)
            processed_gain_path = os.path.join(
                self.temp_dir, "gain_processed.shp")
            processed_loss_path = os.path.join(
                self.temp_dir, "loss_processed.shp")

            if os.path.exists(processed_gain_path):
                gain_input_path = processed_gain_path
                self.log_message(
                    "Found 'gain_processed.shp'. Using it for Smoothify.")
            if os.path.exists(processed_loss_path):
                loss_input_path = processed_loss_path
                self.log_message(
                    "Found 'loss_processed.shp'. Using it for Smoothify.")

            # Prioridade 2: Se não encontrou os processados, procura pelos filtrados padrão
            if not gain_input_path:
                filtered_gain_path = os.path.join(
                    self.temp_dir, "gain_filtered.shp")
                if os.path.exists(filtered_gain_path):
                    gain_input_path = filtered_gain_path
                    self.log_message(
                        "Found 'gain_filtered.shp'. Using it for Smoothify.")

            if not loss_input_path:
                filtered_loss_path = os.path.join(
                    self.temp_dir, "loss_filtered.shp")
                if os.path.exists(filtered_loss_path):
                    loss_input_path = filtered_loss_path
                    self.log_message(
                        "Found 'loss_filtered.shp'. Using it for Smoothify.")

            # Fallback: Se nenhum arquivo foi encontrado, tenta exportar da aba de Métricas
            if not gain_input_path and not loss_input_path:
                self.log_message(
                    "No pre-existing vector files found. Attempting to export from Metrics tab...")
                try:
                    self._export_filtered_vectors_to_temp()
                    # Re-verifica os caminhos após a exportação
                    gain_input_path = self.filtered_gain_vector
                    loss_input_path = self.filtered_loss_vector
                except Exception as e:
                    QMessageBox.warning(
                        self.dialog, "Error", f"Could not obtain filtered vectors. Ensure layers 'Gain/Loss Vectors (with Metrics)' exist and have been filtered.\n\nError: {e}")
                    self.log_message(
                        f"Error during fallback export in Smoothify: {str(e)}")
                    return

            # Verificação final se temos pelo menos um arquivo para processar
            if not gain_input_path and not loss_input_path:
                QMessageBox.warning(self.dialog, "Input Not Found",
                                    "Could not find or create any input vector files for Smoothify. Please complete the previous steps.")
                return

            # 3. Processar os vetores encontrados
            if gain_input_path and os.path.exists(gain_input_path):
                gain_layer = QgsVectorLayer(
                    gain_input_path, "Input for Smoothify (Gain)", "ogr")
                if gain_layer.isValid():
                    self.smoothed_gain_vector_path = os.path.join(
                        self.temp_dir, "smoothed_gain_vector.shp")
                    self._process_layer_with_smoothify(
                        gain_layer, self.smoothed_gain_vector_path, segment_length, smooth_iterations, preserve_area, area_tolerance, "Smoothed Gain Vector")
                else:
                    self.log_message(
                        f"Warning: Could not load gain layer from {gain_input_path}")

            if loss_input_path and os.path.exists(loss_input_path):
                loss_layer = QgsVectorLayer(
                    loss_input_path, "Input for Smoothify (Loss)", "ogr")
                if loss_layer.isValid():
                    self.smoothed_loss_vector_path = os.path.join(
                        self.temp_dir, "smoothed_loss_vector.shp")
                    self._process_layer_with_smoothify(
                        loss_layer, self.smoothed_loss_vector_path, segment_length, smooth_iterations, preserve_area, area_tolerance, "Smoothed Loss Vector")
                else:
                    self.log_message(
                        f"Warning: Could not load loss layer from {loss_input_path}")

            QMessageBox.information(
                self.dialog, "Success", "Smoothify applied successfully. Smoothed vectors loaded into the project.")

        except Exception as e:
            self.log_message(f"Error applying Smoothify: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error applying Smoothify: {str(e)}")

    def _process_layer_with_smoothify(self, input_layer, output_path, segment_length, smooth_iterations, preserve_area, area_tolerance, output_name):
        """Aplica Smoothify em uma camada vetorial e salva o resultado."""

        # 1. Configurar o writer
        fields = input_layer.fields()
        writer = QgsVectorFileWriter(
            output_path, 'UTF-8', fields, QgsWkbTypes.Polygon, input_layer.crs(), 'ESRI Shapefile')

        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise Exception(
                f"Error creating output file {output_path}: {writer.errorMessage()}")

        # 2. Iterar sobre as features e aplicar Smoothify
        for feature in input_layer.getFeatures():
            geom = feature.geometry()
            if not geom or geom.isEmpty():
                continue

            # Converter QgsGeometry para Shapely Geometry (Correção Problema 4)
            # O método QgsWkbTypes.geometryToShapely() não está disponível em algumas versões do QGIS.
            # Usamos a conversão via WKT, que é mais robusta.
            shapely_geom = shapely_loads(geom.asWkt())

            # Aplicar Smoothify
            smoothed_shapely_geom = smoothify_geometry(
                shapely_geom, segment_length, smooth_iterations, preserve_area, area_tolerance
            )

            # Converter Shapely Geometry de volta para QgsGeometry
            smoothed_qgs_geom = QgsGeometry.fromWkt(smoothed_shapely_geom.wkt)

            # Criar nova feature com a geometria suavizada
            new_feature = QgsFeature(fields)
            new_feature.setGeometry(smoothed_qgs_geom)
            new_feature.setAttributes(feature.attributes())

            writer.addFeature(new_feature)

        del writer  # Fecha o arquivo

        # 3. Carregar a camada suavizada no projeto
        self._load_vector_to_project(output_path, output_name)

    def export_filtered_vectors(self, export_dir=None, is_internal_call=False):
        """
        Exporta as features selecionadas (filtradas) para um shapefile usando QgsVectorFileWriter.
        Esta é a versão robusta que evita erros do framework de processamento.
        """
        if not export_dir:
            export_dir = QFileDialog.getExistingDirectory(
                self.dialog, "Select Output Directory for Filtered Vectors")
            if not export_dir:
                return None, None

        try:
            # Avoid ensuring temp dir here to prevent recursion with _ensure_temp_dir().
            # Caller should ensure `self.temp_dir` when required. Just gather layers.
            gain_layers = QgsProject.instance().mapLayersByName("Gain Vectors (with Metrics)")
            loss_layers = QgsProject.instance().mapLayersByName("Loss Vectors (with Metrics)")

            gain_output_path = None
            loss_output_path = None

            # Função auxiliar para escrever o shapefile de forma segura
            def write_shapefile(layer, output_path):
                if not layer:
                    return False

                if layer.selectedFeatureCount() == 0:
                    # Try common 'val' values used in the plugin outputs (255 preferred)
                    tried = []
                    try:
                        layer.selectByExpression('"is_valid" = 1 AND "val" = 255')
                        tried.append('val=255')
                    except Exception:
                        pass
                    if layer.selectedFeatureCount() == 0:
                        try:
                            layer.selectByExpression('"is_valid" = 1 AND "val" = 0')
                            tried.append('val=0')
                        except Exception:
                            pass

                if layer.selectedFeatureCount() == 0:
                    # Final fallback: select only valid features
                    try:
                        layer.selectByExpression('"is_valid" = 1')
                        tried.append('is_valid only')
                    except Exception:
                        pass

                if layer.selectedFeatureCount() == 0:
                    self.log_message(
                        f"No features to export for layer {layer.name()} (tried: {tried}).")
                    return False

                writer = QgsVectorFileWriter(
                    output_path, 'UTF-8', layer.fields(),
                    layer.wkbType(), layer.crs(), "ESRI Shapefile"
                )

                if writer.hasError() != QgsVectorFileWriter.NoError:
                    raise Exception(
                        f"Failed to create shapefile writer for {output_path}: {writer.errorMessage()}")

                for feature in layer.selectedFeatures():
                    writer.addFeature(feature)

                del writer
                return True

            # Exporta Gain Vectors
            if gain_layers:
                gain_layer = gain_layers[0]
                gain_output_path = os.path.join(
                    export_dir, "gain_filtered.shp")
                if write_shapefile(gain_layer, gain_output_path):
                    self.log_message(
                        f"Filtered Gain Vectors exported to {gain_output_path} ({gain_layer.selectedFeatureCount()} features)")
                    if not is_internal_call:
                        QMessageBox.information(
                            self.dialog, "Success", f"Filtered Gain Vectors exported to {gain_output_path}")
                elif not is_internal_call:
                    QMessageBox.warning(
                        self.dialog, "Warning", "No valid features to export for Gain layer.")

            # Exporta Loss Vectors
            if loss_layers:
                loss_layer = loss_layers[0]
                loss_output_path = os.path.join(
                    export_dir, "loss_filtered.shp")
                if write_shapefile(loss_layer, loss_output_path):
                    self.log_message(
                        f"Filtered Loss Vectors exported to {loss_output_path} ({loss_layer.selectedFeatureCount()} features)")
                    if not is_internal_call:
                        QMessageBox.information(
                            self.dialog, "Success", f"Filtered Loss Vectors exported to {loss_output_path}")
                elif not is_internal_call:
                    QMessageBox.warning(
                        self.dialog, "Warning", "No valid features to export for Loss layer.")

            return gain_output_path, loss_output_path

        except Exception as e:
            error_msg = f"Error exporting filtered vectors: {str(e)}"
            self.log_message(error_msg)
            if not is_internal_call:
                QMessageBox.critical(self.dialog, "Error", error_msg)
            raise Exception(error_msg)



    def _ensure_temp_dir(self):
        """Ensure plugin temp directory exists and is writable. Raises on failure."""
        if not hasattr(self, 'temp_dir') or not self.temp_dir:
            self.temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
        except Exception as e:
            self.log_message(f"Could not create temp dir '{self.temp_dir}': {e}")
            raise
        # Check writability
        try:
            test_path = os.path.join(self.temp_dir, ".write_test")
            with open(test_path, 'w') as f:
                f.write('ok')
            os.remove(test_path)
        except Exception as e:
            self.log_message(f"Temp dir not writable '{self.temp_dir}': {e}")
            raise

    def _export_filtered_vectors_to_temp_fixed(self):
        """Exporta os vetores filtrados para o diretório temporário do plugin (lógica movida para cá)."""
        self.log_message(
            "Attempting to export filtered vectors to temp directory for Smoothify.")
        try:
            gain_output_path, loss_output_path = self.export_filtered_vectors(
                export_dir=self.temp_dir, is_internal_call=True)

            if gain_output_path and os.path.exists(gain_output_path):
                self.filtered_gain_vector = gain_output_path
            else:
                self.filtered_gain_vector = None

            if loss_output_path and os.path.exists(loss_output_path):
                self.filtered_loss_vector = loss_output_path
            else:
                self.filtered_loss_vector = None

            self.log_message(
                f"Filtered vectors exported to temp: Gain={self.filtered_gain_vector}, Loss={self.filtered_loss_vector}")

            if not self.filtered_gain_vector and not self.filtered_loss_vector:
                # Não levanta exceção aqui, apenas loga e permite que o processo continue
                # se for o caso de não haver features filtradas.
                self.log_message(
                    "WARNING: Export process completed, but no output files were generated (no features to export).")

        except Exception as e:
            self.log_message(
                f"Failed during _export_filtered_vectors_to_temp_fixed: {e}")
            # Levanta a exceção para ser capturada por next_to_metrics
            raise Exception(f"Temp dir error before computing metrics: {e}")

    def generate_centroids(self):
        """Gera centroides a partir dos vetores filtrados (gain/loss) e carrega no projeto.

        - Procura por camadas filtradas exportadas em `self.filtered_gain_vector` e
          `self.filtered_loss_vector` ou tenta exportá-las para o diretório temporário.
        - Calcula centroides das feições selecionadas/filtradas e salva em shapefile
          temporário dentro de `self.temp_dir` como `centroids_gain.shp` e
          `centroids_loss.shp`.
        - Adiciona as camadas de centroides ao projeto QGIS.
        """
        try:
            # Candidate filenames to look for (in project layers or temp directory)
            candidate_names = {
                'gain': [
                    'gain_filtered.shp',
                    'gain_processed.shp',
                    'smoothed_gain_vector.shp'
                ],
                'loss': [
                    'loss_filtered.shp',
                    'loss_processed.shp',
                    'smoothed_loss_vector.shp'
                ]
            }

            # Helper to normalize layer source to a filesystem path when possible
            from urllib.parse import unquote

            def _src_to_path(src: str) -> str:
                if not src:
                    return ''
                s = src.replace('\\', '/')
                # shapefile sources in QGIS sometimes have a | at the end with layer options
                if '|' in s:
                    s = s.split('|')[0]
                # file URI
                if s.startswith('file://'):
                    p = s[7:]
                    # On Windows the file URI may start with an extra leading '/'
                    if os.name == 'nt' and p.startswith('/') and len(p) > 2 and p[2] == ':':
                        p = p[1:]
                    return unquote(p)
                return unquote(s)

            # Gather candidates from project layers and known temp files / attributes
            candidates = []  # list of dicts: {'role','path','label'}

            # 1) Inspect loaded project layers
            for lyr in QgsProject.instance().mapLayers().values():
                try:
                    src = lyr.source()
                except Exception:
                    try:
                        src = lyr.dataProvider().dataSourceUri()
                    except Exception:
                        src = ''

                if not src:
                    continue

                path = _src_to_path(src)
                base = os.path.basename(path).lower()
                for role, names in candidate_names.items():
                    for name in names:
                        if base == name.lower() or name.lower() in path.lower():
                            candidates.append({'role': role, 'path': path, 'label': f"{role.title()}: {os.path.basename(path)} (layer {lyr.name()})"})

            # 2) Inspect attributes and temp dir files (fallbacks)
            # - self.filtered_gain_vector / filtered_loss_vector
            for attr_name, role_hint in [('filtered_gain_vector', 'gain'), ('filtered_loss_vector', 'loss')]:
                p = getattr(self, attr_name, None)
                if p:
                    p_norm = _src_to_path(p)
                    if p_norm and os.path.exists(p_norm):
                        candidates.append({'role': role_hint, 'path': p_norm, 'label': f"{role_hint.title()}: {os.path.basename(p_norm)} (filtered attr)"})

            # - look for standard filenames in temp_dir
            for role, names in candidate_names.items():
                for name in names:
                    temp_path = os.path.join(self.temp_dir, name)
                    if os.path.exists(temp_path):
                        candidates.append({'role': role, 'path': temp_path, 'label': f"{role.title()}: {name} (temp)"})

            # Deduplicate by path (keep first)
            seen = set()
            uniq = []
            for c in candidates:
                pnorm = os.path.normpath(c['path']) if c.get('path') else c.get('path')
                if not pnorm:
                    continue
                if pnorm in seen:
                    continue
                seen.add(pnorm)
                uniq.append(c)
            candidates = uniq

            # If no candidates found, try exporting filtered vectors to temp then re-scan
            if not candidates:
                try:
                    self._export_filtered_vectors_to_temp()
                except Exception as e:
                    self.log_message(f"Could not export filtered vectors to temp: {e}")

                # re-check temp paths
                for role, names in candidate_names.items():
                    for name in names:
                        temp_path = os.path.join(self.temp_dir, name)
                        if os.path.exists(temp_path):
                            candidates.append({'role': role, 'path': temp_path, 'label': f"{role.title()}: {name} (temp)"})

            if not candidates:
                QMessageBox.warning(self.dialog, 'Warning', 'No candidate input vector files found for centroids.')
                self.log_message('No candidate centroid inputs found in project or temp dir.')
                return

            # Build selection dialog so user can pick which inputs to generate centroids for
            dlg = QDialog(self.dialog)
            dlg.setWindowTitle('Select Inputs for Centroids')
            dlg_layout = QVBoxLayout(dlg)
            dlg_layout.addWidget(QLabel('Select which input vector(s) to generate centroids from:'))

            chk_list = []
            for c in candidates:
                chk = QCheckBox(c['label'])
                chk.setChecked(True)
                dlg_layout.addWidget(chk)
                chk_list.append(chk)

            btn_box = QHBoxLayout()
            ok_btn = QPushButton('Generate')
            cancel_btn = QPushButton('Cancel')
            btn_box.addWidget(ok_btn)
            btn_box.addWidget(cancel_btn)
            dlg_layout.addLayout(btn_box)

            ok_btn.clicked.connect(dlg.accept)
            cancel_btn.clicked.connect(dlg.reject)

            if dlg.exec_() != QDialog.Accepted:
                self.log_message('Centroid generation cancelled by user.')
                return

            selected = [c for c, ch in zip(candidates, chk_list) if ch.isChecked()]
            if not selected:
                QMessageBox.information(self.dialog, 'Info', 'No inputs selected for centroids.')
                return

            created = []
            for sel in selected:
                in_src = sel['path']
                # normalize path again
                in_path = _src_to_path(in_src)
                if not in_path or not os.path.exists(in_path):
                    self.log_message(f"Skipping missing input: {in_src}")
                    continue

                out_name = f"centroids_{sel['role']}_{os.path.splitext(os.path.basename(in_path))[0]}.shp"
                out_path = os.path.join(self.temp_dir, out_name)

                try:
                    params = {
                        'INPUT': in_path,
                        'ALL_PARTS': False,
                        'OUTPUT': out_path
                    }
                    result = processing.run('native:centroids', params)
                    out_res = result.get('OUTPUT') or result.get('OUTPUT_LAYER') or result.get('OUTPUT_RASTER')
                    final_path = out_res if out_res else out_path
                    if final_path and os.path.exists(final_path):
                        layer_name = f"Centroids - {sel['role'].title()} - {os.path.splitext(os.path.basename(in_path))[0]}"
                        cent_lyr = QgsVectorLayer(final_path, layer_name, 'ogr')
                        if cent_lyr.isValid():
                            QgsProject.instance().addMapLayer(cent_lyr)
                            created.append(final_path)
                            self.log_message(f"Centroids generated and added: {final_path}")
                        else:
                            self.log_message(f"Centroid output invalid: {final_path}")
                    else:
                        self.log_message(f"Centroid algorithm did not return output for {in_path}")
                except Exception as e:
                    self.log_message(f"Error creating centroids for {in_path}: {e}")

            if created:
                QMessageBox.information(self.dialog, 'Success', f"Centroids generated and loaded ({len(created)}). Check project layers.")
            else:
                QMessageBox.information(self.dialog, 'Info', 'No centroid layers created.')

        except Exception as e:
            self.log_message(f"Error generating centroids: {e}")
            QMessageBox.warning(self.dialog, 'Error', f'Error generating centroids: {e}')

    # --- Smoothify Functions (Copied from smoothify_core.py) ---


def _chaikin_corner_cutting(
    geom: Polygon | LineString, num_iterations: int = 1, reverse: bool = False
) -> Polygon | LineString:
    """Apply Chaikin's corner cutting algorithm to smooth a geometry.

    Chaikin's algorithm iteratively replaces each line segment with two new segments
    by cutting corners at 1/4 and 3/4 positions, creating a smooth curve. This
    implementation uses vectorized NumPy operations for performance and handles
    both closed (Polygon) and open (LineString) geometries.
    """

    is_closed = isinstance(geom, Polygon)
    points = np.array(
        geom.exterior.coords if is_closed else geom.coords, dtype=np.float64
    )

    if is_closed:
        # Remove duplicate endpoint for closed rings
        points = points[:-1]
        endpoints = None
    else:
        # Store endpoints for open linestrings
        endpoints = (points[0], points[-1])

    if reverse:
        points = points[::-1]

    for _ in range(num_iterations):
        # Get point pairs for corner cutting
        if is_closed:
            p0 = points
            p1 = np.roll(points, -1, axis=0)
        else:
            p0 = points[:-1]
            p1 = points[1:]

        # Vectorized smoothing at 1/4 and 3/4 positions
        # Pre-allocate result array for better performance
        n_new_points = len(p0) * 2
        points = np.empty((n_new_points, 2), dtype=np.float64)
        points[0::2] = 0.75 * p0 + 0.25 * p1  # q points
        points[1::2] = 0.25 * p0 + 0.75 * p1  # r points

    if not is_closed:
        # Restore original endpoints for open linestrings
        points = np.vstack([endpoints[0], points, endpoints[1]])

    # Reconstruct the geometry
    if is_closed:
        # Close the ring for Polygon
        points = np.vstack([points, points[0]])
        return Polygon(points)
    else:
        return LineString(points)


def _smooth_geometry(
    geom: BaseGeometry,
    segment_length: float,
    smooth_iterations: int,
    preserve_area: bool,
    area_tolerance: float,
) -> BaseGeometry:
    """Internal function to smooth a single geometry."""

    if geom.is_empty:
        return geom

    # 1. Segmentize (add intermediate vertices)
    # This is crucial for Chaikin's algorithm to work well on pixelated geometries
    # The number of segments is calculated to ensure segments are roughly segment_length long
    if isinstance(geom, (Polygon, LineString)):
        # Calculate number of segments to add
        length = geom.length
        num_segments = max(1, int(np.ceil(length / segment_length)))
        geom = geom.segmentize(length / num_segments)
    elif isinstance(geom, LinearRing):
        # LinearRing is treated as a closed LineString for segmentize
        length = geom.length
        num_segments = max(1, int(np.ceil(length / segment_length)))
        # Convert to LineString, segmentize, then back to LinearRing
        ls = LineString(geom.coords)
        ls = ls.segmentize(length / num_segments)
        geom = LinearRing(ls.coords)

    # 2. Apply Chaikin's corner cutting
    if isinstance(geom, (Polygon, LineString)):
        smoothed_geom = _chaikin_corner_cutting(
            geom, num_iterations=smooth_iterations
        )
    elif isinstance(geom, LinearRing):
        # Apply to LinearRing's coordinates
        ls = LineString(geom.coords)
        smoothed_ls = _chaikin_corner_cutting(
            ls, num_iterations=smooth_iterations
        )
        smoothed_geom = LinearRing(smoothed_ls.coords)
    else:
        # Unsupported geometry type for smoothing (e.g., Point, MultiPoint)
        return geom

    # 3. Optional: Preserve area for Polygons
    if preserve_area and isinstance(smoothed_geom, Polygon):
        original_area = geom.area
        smoothed_area = smoothed_geom.area

        # Use brentq to find the buffer distance that restores the area
        def area_error(buffer_dist):
            buffered_geom = smoothed_geom.buffer(buffer_dist)
            # Ensure the buffered geometry is valid and a Polygon
            if not buffered_geom.is_valid:
                buffered_geom = make_valid(buffered_geom)
            if isinstance(buffered_geom, Polygon):
                return buffered_geom.area - original_area
            elif isinstance(buffered_geom, MultiPolygon):
                # If it becomes a MultiPolygon, use the area of the largest part
                return max(p.area for p in buffered_geom.geoms) - original_area
            else:
                # If it becomes another type (e.g., LineString, Point),
                # this is an edge case, return a large error
                return 1e12

        # Find the root (buffer distance)
        # The search range is typically small, e.g., -10 to 10 map units
        try:
            buffer_distance = brentq(
                area_error, -10.0, 10.0, xtol=area_tolerance)
            smoothed_geom = smoothed_geom.buffer(buffer_distance)
            if not smoothed_geom.is_valid:
                smoothed_geom = make_valid(smoothed_geom)
        except ValueError:
            # Root not found in the interval, or other error. Return the smoothed geometry without area preservation.
            pass

    return smoothed_geom


def smoothify_geometry(
    geom: BaseGeometry,
    segment_length: float,
    smooth_iterations: int = 3,
    preserve_area: bool = True,
    area_tolerance: float = 0.01,
) -> BaseGeometry:
    """
    Applies Chaikin's corner cutting algorithm to smooth a single geometry.

    Parameters
    ----------
    geom : BaseGeometry
        The geometry to smooth.
    segment_length : float
        Resolution of the original raster data in map units. Used for segmentization.
    smooth_iterations : int, optional
        Number of Chaikin corner-cutting iterations (typically 3-5). The default is 3.
    preserve_area : bool, optional
        Whether to restore original area after smoothing via buffering (applies to Polygons only). The default is True.
    area_tolerance : float, optional
        Percentage of original area allowed as error (e.g., 0.01 = 0.01% error = 99.99% preservation).
        Only affects Polygons when preserve_area=True. The default is 0.01.

    Returns
    -------
    BaseGeometry
        The smoothed geometry.
    """
    if isinstance(geom, (Polygon, LineString, LinearRing)):
        return _smooth_geometry(
            geom, segment_length, smooth_iterations, preserve_area, area_tolerance
        )
    elif isinstance(geom, GeometryCollection):
        # Recursively smooth geometries in the collection
        smoothed_geoms = [
            smoothify_geometry(
                g, segment_length, smooth_iterations, preserve_area, area_tolerance
            )
            for g in geom.geoms
        ]
        # Attempt to union the results back into a single geometry if possible
        try:
            return unary_union(smoothed_geoms)
        except Exception:
            # If union fails, return the collection
            return GeometryCollection(smoothed_geoms)
    elif hasattr(geom, "geoms"):
        # Handle Multi-geometries (MultiPolygon, MultiLineString)
        # Smooth each part, taking care to flatten nested Multi-geometries
        parts = []
        for g in geom.geoms:
            sm = _smooth_geometry(
                g, segment_length, smooth_iterations, preserve_area, area_tolerance
            )
            # If the result is a MultiPolygon (or other multi), extend its parts
            if isinstance(sm, MultiPolygon):
                parts.extend(list(sm.geoms))
            elif hasattr(sm, 'geoms'):
                # generic multi-geometry (e.g., MultiLineString)
                parts.extend(list(sm.geoms))
            else:
                parts.append(sm)

        # Reconstruct appropriate multi-type
        if isinstance(geom, MultiPolygon):
            # ensure all parts are Polygons
            poly_parts = [p for p in parts if isinstance(p, Polygon)]
            return MultiPolygon(poly_parts)
        else:
            # For other multi-types (e.g., MultiLineString), try to rebuild using unary_union
            try:
                return unary_union(parts)
            except Exception:
                return geom
    else:
        # Other types (Point, MultiPoint) are returned as is
        return geom

    def next_to_export(self):
        """Avança para o tab Export & Finish (sem calcular nada automaticamente)."""
        try:
            # Pega o atual (deve ser 8 pra Metrics)
            current_index = self.dialog.tabWidget.currentIndex()
            next_index = current_index + 1  # Próximo (9 pra Export & Finish)
            # Habilita o tab (e seus botões filhos)
            self.dialog.tabWidget.setTabEnabled(next_index, True)
            self.dialog.tabWidget.setCurrentIndex(next_index)  # Avança
            self.log_message(
                f"➡️ Advanced from tab {current_index} to {next_index} (Export & Finish). Buttons now enabled.")
        except Exception as e:
            self.log_message(
                f"Error advancing to Export & Finish tab: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error advancing: {str(e)}")

    def orthogonalize_or_simplify(self):
        if not self.gain_mask_path or not self.loss_mask_path or not os.path.exists(self.gain_mask_path) or not os.path.exists(self.loss_mask_path):
            QMessageBox.warning(self.dialog, "Warning",
                                "Generate the gain and loss masks first.")
            return

        ds_gain = gdal.Open(self.gain_mask_path)
        ds_loss = gdal.Open(self.loss_mask_path)
        arr_gain = ds_gain.ReadAsArray()
        arr_loss = ds_loss.ReadAsArray()
        preview_gain = arr_gain[::4,
                                ::4] if arr_gain.shape[0] > 800 else arr_gain
        preview_loss = arr_loss[::4,
                                ::4] if arr_loss.shape[0] > 800 else arr_loss
        ds_gain = None
        ds_loss = None
        arr_bin_gain = (preview_gain == 255).astype(np.uint8)
        arr_bin_loss = (preview_loss == 255).astype(np.uint8)

        preview_dialog = QDialog(self.dialog)
        preview_dialog.setWindowTitle(
            "Vectorization and Metrics Filter Preview")
        preview_dialog.resize(1200, 800)
        layout = QVBoxLayout()

        min_area_slider = QSlider(Qt.Horizontal)
        min_area_slider.setRange(1, 1000)
        min_area_slider.setValue(50)
        min_area_label = QLabel(f"{min_area_slider.value()} px")
        min_area_slider.valueChanged.connect(
            lambda val: min_area_label.setText(f"{val} px"))
        layout.addWidget(QLabel("Minimum polygon area:"))
        layout.addWidget(min_area_slider)
        layout.addWidget(min_area_label)

        min_compact_slider = QSlider(Qt.Horizontal)
        min_compact_slider.setRange(1, 100)
        min_compact_slider.setValue(30)
        min_compact_label = QLabel(f"{min_compact_slider.value()/100:.2f}")
        min_compact_slider.valueChanged.connect(
            lambda val: min_compact_label.setText(f"{val/100:.2f}"))
        layout.addWidget(QLabel("Minimum compactness (buildings):"))
        layout.addWidget(min_compact_slider)
        layout.addWidget(min_compact_label)

        ortho_tolerance_slider = QSlider(Qt.Horizontal)
        ortho_tolerance_slider.setRange(0, 5)
        ortho_tolerance_slider.setValue(1)
        ortho_label = QLabel(
            f"Orthogonalization Tolerance: {ortho_tolerance_slider.value()/2:.1f}")
        ortho_tolerance_slider.valueChanged.connect(
            lambda val: ortho_label.setText(f"Orthogonalization Tolerance: {val/2:.1f}"))
        layout.addWidget(QLabel("Tolerance for Orthogonalization:"))
        layout.addWidget(QLabel(
            "Higher value: allows more angular deviation; Lower value: forces stricter orthogonality"))
        layout.addWidget(ortho_tolerance_slider)
        layout.addWidget(ortho_label)

        fig_gain, ax_gain = plt.subplots(figsize=(7, 5))
        canvas_gain = FigureCanvas(fig_gain)
        layout.addWidget(
            QLabel("Vectorization Preview Gain (Year 2 - Year 1):"))
        layout.addWidget(canvas_gain)

        fig_loss, ax_loss = plt.subplots(figsize=(7, 5))
        canvas_loss = FigureCanvas(fig_loss)
        layout.addWidget(
            QLabel("Vectorization Preview Loss (Year 1 - Year 2):"))
        layout.addWidget(canvas_loss)

        # Throttle updates to avoid heavy repeated processing causing instability
        if not hasattr(self, '_preview_update_timer'):
            self._preview_update_timer = QTimer()
            self._preview_update_timer.setSingleShot(True)

        def _do_update_preview():
            try:
                # Defensive checks
                if 'arr_bin_gain' not in locals() and 'arr_bin_gain' not in globals():
                    self.log_message('arr_bin_gain missing in preview context')
                    return
                if 'arr_bin_loss' not in locals() and 'arr_bin_loss' not in globals():
                    self.log_message('arr_bin_loss missing in preview context')
                    return

                # Compute filtered masks based on current slider values
                try:
                    labeled_gain, num_gain = ndi.label(arr_bin_gain)
                except Exception:
                    labeled_gain = None
                    num_gain = 0

                filtered_gain = np.zeros_like(arr_bin_gain) if num_gain > 0 else np.zeros((0,))
                for i in range(1, num_gain + 1):
                    component = (labeled_gain == i)
                    coords = np.argwhere(component)
                    if coords.size == 0:
                        continue
                    area = coords.shape[0]
                    if area < min_area_slider.value():
                        continue
                    min_y, min_x = coords.min(0)
                    max_y, max_x = coords.max(0)
                    width = max_x - min_x + 1
                    height = max_y - min_y + 1
                    perimeter = 2 * (width + height)
                    compacidade = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
                    if compacidade < min_compact_slider.value() / 100:
                        continue
                    filtered_gain[component] = 1

                ax_gain.clear()
                if filtered_gain.size != 0:
                    ax_gain.imshow(filtered_gain, cmap='gray')
                ax_gain.set_title('Preview Gain Mask', fontsize=10)
                try:
                    canvas_gain.draw_idle()
                except Exception:
                    canvas_gain.draw()

                try:
                    labeled_loss, num_loss = ndi.label(arr_bin_loss)
                except Exception:
                    labeled_loss = None
                    num_loss = 0

                filtered_loss = np.zeros_like(arr_bin_loss) if num_loss > 0 else np.zeros((0,))
                for i in range(1, num_loss + 1):
                    component = (labeled_loss == i)
                    coords = np.argwhere(component)
                    if coords.size == 0:
                        continue
                    area = coords.shape[0]
                    if area < min_area_slider.value():
                        continue
                    min_y, min_x = coords.min(0)
                    max_y, max_x = coords.max(0)
                    width = max_x - min_x + 1
                    height = max_y - min_y + 1
                    perimeter = 2 * (width + height)
                    compacidade = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
                    if compacidade < min_compact_slider.value() / 100:
                        continue
                    filtered_loss[component] = 1

                ax_loss.clear()
                if filtered_loss.size != 0:
                    ax_loss.imshow(filtered_loss, cmap='gray')
                ax_loss.set_title('Preview Loss Mask', fontsize=10)
                try:
                    canvas_loss.draw_idle()
                except Exception:
                    canvas_loss.draw()

            except Exception as e:
                import traceback
                self.log_message(f"Error in preview update: {e}\n" + traceback.format_exc())

        # internal connect for timer
        if not self._preview_update_timer.receivers():
            try:
                self._preview_update_timer.timeout.connect(_do_update_preview)
            except Exception:
                # If connect fails, still allow calling directly
                pass

        def schedule_preview_update():
            # start/reset debounce timer (200 ms)
            try:
                self._preview_update_timer.start(200)
            except Exception:
                # fallback to direct call if timer fails
                _do_update_preview()

        min_area_slider.valueChanged.connect(lambda v: schedule_preview_update())
        min_compact_slider.valueChanged.connect(lambda v: schedule_preview_update())
        # simplify_tolerance_slider.valueChanged.connect
        ortho_tolerance_slider.valueChanged.connect(lambda v: schedule_preview_update())

        def apply_vectorization():
            ortho_tol = ortho_tolerance_slider.value() / 2.0
            min_area = min_area_slider.value()
            min_compact = min_compact_slider.value() / 100

            # Defensive checks: ensure gain/loss mask paths exist and can be opened
            if not self.gain_mask_path or not os.path.exists(self.gain_mask_path):
                QMessageBox.warning(preview_dialog, "Error", "Gain mask not found. Generate masks first.")
                return
            if not self.loss_mask_path or not os.path.exists(self.loss_mask_path):
                QMessageBox.warning(preview_dialog, "Error", "Loss mask not found. Generate masks first.")
                return

            ds_gain_full = gdal.Open(self.gain_mask_path)
            ds_loss_full = gdal.Open(self.loss_mask_path)
            if ds_gain_full is None or ds_loss_full is None:
                QMessageBox.warning(preview_dialog, "Error", "Failed to open gain/loss mask datasets. Check files and GDAL support.")
                self.log_message("Failed to open gain/loss mask datasets for vectorization preview")
                return

            arr_gain_full = ds_gain_full.ReadAsArray()
            arr_loss_full = ds_loss_full.ReadAsArray()
            arr_bin_gain_full = (arr_gain_full == 255).astype(np.uint8)
            arr_bin_loss_full = (arr_loss_full == 255).astype(np.uint8)

            out_gain_path = os.path.join(
                self.temp_dir, "vector_preview_gain.tif")
            driver = gdal.GetDriverByName('GTiff')
            out_ds_gain = driver.Create(
                out_gain_path, ds_gain_full.RasterXSize, ds_gain_full.RasterYSize, 1, gdal.GDT_Byte)
            out_ds_gain.SetGeoTransform(ds_gain_full.GetGeoTransform())
            out_ds_gain.SetProjection(ds_gain_full.GetProjection())
            labeled_gain, num_gain = ndi.label(arr_bin_gain_full)
            filtered_gain = np.zeros_like(arr_bin_gain_full)
            for i in range(1, num_gain + 1):
                component = (labeled_gain == i)
                coords = np.argwhere(component)
                area = coords.shape[0]
                if area < min_area:
                    continue

                min_y, min_x = coords.min(0)
                max_y, max_x = coords.max(0)
                width = max_x - min_x + 1
                height = max_y - min_y + 1
                perimeter = 2 * (width + height)
                compacidade = 4 * np.pi * area / \
                    (perimeter ** 2) if perimeter > 0 else 0
                if compacidade < min_compact:
                    continue

                filtered_gain[component] = 1

            # Correção Problema 3: Define 0 como NoData para que o polygonize ignore o fundo
            out_ds_gain.GetRasterBand(1).SetNoDataValue(0)
            out_ds_gain.GetRasterBand(1).WriteArray(filtered_gain * 255)
            out_ds_gain = None

            out_loss_path = os.path.join(
                self.temp_dir, "vector_preview_loss.tif")
            out_ds_loss = driver.Create(
                out_loss_path, ds_loss_full.RasterXSize, ds_loss_full.RasterYSize, 1, gdal.GDT_Byte)
            out_ds_loss.SetGeoTransform(ds_loss_full.GetGeoTransform())
            out_ds_loss.SetProjection(ds_loss_full.GetProjection())
            labeled_loss, num_loss = ndi.label(arr_bin_loss_full)
            filtered_loss = np.zeros_like(arr_bin_loss_full)
            for i in range(1, num_loss + 1):
                component = (labeled_loss == i)
                coords = np.argwhere(component)
                area = coords.shape[0]
                if area < min_area:
                    continue
                min_y, min_x = coords.min(0)
                max_y, max_x = coords.max(0)
                width = max_x - min_x + 1
                height = max_y - min_y + 1

                perimeter = 2 * (width + height)
                compacidade = 4 * np.pi * area / \
                    (perimeter ** 2) if perimeter > 0 else 0
                if compacidade < min_compact:
                    continue

                filtered_loss[component] = 1

            # Correção Problema 3: Define 0 como NoData para que o polygonize ignore o fundo
            out_ds_loss.GetRasterBand(1).SetNoDataValue(0)
            out_ds_loss.GetRasterBand(1).WriteArray(filtered_loss * 255)
            out_ds_loss = None

            ds_gain_full = None
            ds_loss_full = None

            self.gain_vector_path = os.path.join(
                self.temp_dir, "preview_gain_vector_raw.shp")
            processing.run("gdal:polygonize", {
                "INPUT": out_gain_path,
                "BAND": 1,
                "FIELD": "val",
                "OUTPUT": self.gain_vector_path
            })

            # Post-process raw gain vector: remove background/noise polygons
            try:
                # compute raster total area in map units to detect giant background polygons
                rds = gdal.Open(out_gain_path)
                gt = rds.GetGeoTransform()
                px_area = abs(gt[1] * gt[5]) if gt is not None else 1.0
                total_raster_area = px_area * rds.RasterXSize * rds.RasterYSize
                rds = None

                raw_gain_layer = QgsVectorLayer(
                    self.gain_vector_path, "raw_gain", "ogr")
                if raw_gain_layer.isValid():
                    clean_gain_path = os.path.join(
                        self.temp_dir, "preview_gain_vector_raw_clean.shp")
                    writer = QgsVectorFileWriter(clean_gain_path, 'UTF-8', raw_gain_layer.fields(
                    ), QgsWkbTypes.Polygon, raw_gain_layer.crs(), 'ESRI Shapefile')
                    for feat in raw_gain_layer.getFeatures():
                        try:
                            gain_field_names = [f.name()
                                                for f in raw_gain_layer.fields()]
                            val = feat['val'] if 'val' in gain_field_names else None
                            if val is None:
                                continue
                            # keep only features that represent objects (val == 255)
                            if int(val) != 255:
                                continue
                            geom = feat.geometry()
                            if geom is None or geom.isEmpty():
                                continue
                            area = geom.area()
                            # discard extremely large polygons (>50% of raster area) as background
                            # Adiciona um filtro de área mais rigoroso para o polígono de fundo.
                            # Se a área for maior que 50% da área total do raster, é considerado fundo.
                            # Isso é crucial para remover o polígono de fundo que pode ter val=255.
                            if total_raster_area > 0 and area > (total_raster_area * 0.5):
                                self.log_message(f"Feature {feat.id()} (val={val}) discarded: area ({area}) > 50% of raster area ({total_raster_area * 0.5})")
                                continue
                            writer.addFeature(feat)
                        except Exception:
                            continue
                    del writer
                    # replace gain_vector_path with cleaned version
                    self.gain_vector_path = clean_gain_path
            except Exception as e:
                self.log_message(
                    f"Warning: failed to clean gain raw vector: {e}")

            # Definir caminhos finais para os vetores ortogonalizados
            self.ortho_gain_path = os.path.join(
                self.temp_dir, "preview_gain_vector_ortho.shp")
            self.ortho_loss_path = os.path.join(
                self.temp_dir, "preview_loss_vector_ortho.shp")

            # Ortho para GAIN
            self._orthogonalize_vector(
                self.gain_vector_path, self.ortho_gain_path, ortho_tol
            )
            self._load_vector_to_project(
                self.ortho_gain_path, "Preview Gain Vector (Ortho)"
            )

            # Criar RAW para LOSS
            loss_vector_raw = os.path.join(
                self.temp_dir, "preview_loss_vector_raw.shp")
            processing.run("gdal:polygonize", {
                "INPUT": out_loss_path,
                "BAND": 1,
                "FIELD": "val",
                "OUTPUT": loss_vector_raw
            })

            # Post-process raw loss vector: remove background/noise polygons
            try:
                rds = gdal.Open(out_loss_path)
                gt = rds.GetGeoTransform()
                px_area = abs(gt[1] * gt[5]) if gt is not None else 1.0
                total_raster_area = px_area * rds.RasterXSize * rds.RasterYSize
                rds = None

                raw_loss_layer = QgsVectorLayer(
                    loss_vector_raw, "raw_loss", "ogr")
                if raw_loss_layer.isValid():
                    clean_loss_path = os.path.join(
                        self.temp_dir, "preview_loss_vector_raw_clean.shp")
                    writer_l = QgsVectorFileWriter(clean_loss_path, 'UTF-8', raw_loss_layer.fields(
                    ), QgsWkbTypes.Polygon, raw_loss_layer.crs(), 'ESRI Shapefile')
                    for feat in raw_loss_layer.getFeatures():
                        try:
                            loss_field_names = [f.name()
                                                for f in raw_loss_layer.fields()]
                            val = feat['val'] if 'val' in loss_field_names else None
                            if val is None:
                                continue
                            # keep only features that represent objects (val == 255)
                            if int(val) != 255:
                                continue
                            geom = feat.geometry()
                            if geom is None or geom.isEmpty():
                                continue
                            area = geom.area()
                            # Adiciona um filtro de área mais rigoroso para o polígono de fundo.
                            # Se a área for maior que 50% da área total do raster, é considerado fundo.
                            # Isso é crucial para remover o polígono de fundo que pode ter val=255.
                            if total_raster_area > 0 and area > (total_raster_area * 0.5):
                                self.log_message(f"Feature {feat.id()} (val={val}) discarded: area ({area}) > 50% of raster area ({total_raster_area * 0.5})")
                                continue
                            writer_l.addFeature(feat)
                        except Exception:
                            continue
                    del writer_l
                    loss_vector_raw = clean_loss_path
            except Exception as e:
                self.log_message(
                    f"Warning: failed to clean loss raw vector: {e}")

            # Ortho para LOSS
            self._orthogonalize_vector(
                loss_vector_raw, self.ortho_loss_path, ortho_tol
            )
            self._load_vector_to_project(
                self.ortho_loss_path, "Preview Loss Vector (Ortho)"
            )

            QMessageBox.information(
                self.dialog, "Success", "Vectorization with filters and orthogonalization applied and loaded in the project."
            )
            preview_dialog.accept()

        apply_button = QPushButton("Apply Vectorization and Orthogonalization")
        apply_button.clicked.connect(apply_vectorization)
        layout.addWidget(apply_button)

        preview_dialog.setLayout(layout)
        update_preview()
        preview_dialog.exec_()

    def _orthogonalize_vector(self, input_path, output_path, ortho_tol):
        layer = QgsVectorLayer(input_path, "temp", "ogr")
        fields = layer.fields()
        writer = QgsVectorFileWriter(
            output_path, 'UTF-8', fields, QgsWkbTypes.Polygon, layer.crs(), 'ESRI Shapefile')
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            orthogonal = geom.densifyByCount(5).orthogonalize(
                ortho_tol) if hasattr(geom, 'orthogonalize') else geom
            feat.setGeometry(orthogonal)
            writer.addFeature(feat)
        del writer

        self._load_vector_to_project(self.gain_vector_path, "Gain Vectors")
        self._load_vector_to_project(self.loss_vector_path, "Loss Vectors")

        # agora sim os combos podem ser atualizados
        # self.populate_vector_combos()

    # Duplicate legacy implementation removed. Use the updated
    # `generate_centroids` implementation above which detects project-loaded
    # file:// URIs, temp files and presents a selection dialog to the user.


