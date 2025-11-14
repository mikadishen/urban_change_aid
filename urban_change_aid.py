from PyQt5.QtCore import QTimer  # Adicione isso no top, após imports Qt
from PyQt5.QtWidgets import (QLabel, QTabWidget, QWidget, QVBoxLayout,
                             QHBoxLayout, QSlider, QSpinBox, QDoubleSpinBox, QPushButton, QDialog, QGridLayout, QScrollArea)
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
    QgsVectorFileWriter, QgsMessageLog, QgsSingleBandGrayRenderer, QgsWkbTypes, )

from qgis.core import QgsDistanceArea, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QVariant, Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QSlider, QRadioButton, QSpinBox, QGroupBox, QCheckBox
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.core import QgsProcessingAlgorithm
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
        export_all_results = None
        self.gain_mask_path = None
        self.loss_mask_path = None
        self.gain_vector_path = None
        self.loss_vector_path = None
        self.filtered_gain_vector = None
        self.filtered_loss_vector = None
        self.centroids_path = None
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

                # Adicione isso no método run(self), após carregar o UI e antes dos connects (depois de self.dialog = uic.loadUi(ui_path))
                # Encontra o tab Centroids (índice 9, ajuste se necessário)
                centroids_tab = self.dialog.tabWidget.widget(
                    9)  # Índice do tab "Centroids & Export"
                if centroids_tab:
                    layout = centroids_tab.layout()  # Assume QVBoxLayout já existe no tab
                    if layout:
                        # Adiciona botão "Generate Heatmaps"
                        generate_heatmaps_btn = QPushButton(
                            "Generate Heatmaps from Centroids")
                        # Insere no topo do layout
                        layout.insertWidget(0, generate_heatmaps_btn)
                        # conecta somente se o método existir para evitar exceptions em tempo de execução
                        if hasattr(self, 'generate_heatmaps'):
                            generate_heatmaps_btn.clicked.connect(
                                self.generate_heatmaps)
                            self.log_message(
                                "Added 'Generate Heatmaps' button to Centroids tab.")
                        else:
                            self.log_message(
                                "Generate heatmaps method not found; button added without connection.")
                    else:
                        self.log_message(
                            "Warning: No layout found in Centroids tab — button not added.")
                else:
                    self.log_message(
                        "Warning: Centroids tab not found — button not added.")

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
                        self.dialog, "Erro", "Botão 'Generate Masks' não encontrado na interface.")

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
            if hasattr(self.dialog, 'spinThresholdYear1'):
                self.dialog.spinThresholdYear1.setMaximum(255)
            if hasattr(self.dialog, 'spinThresholdYear2'):
                self.dialog.spinThresholdYear2.setMaximum(255)

            # Conecta sinais
            self.connect_signals()

            if hasattr(self.dialog, 'previewBandsButton'):
                self.dialog.previewBandsButton.clicked.connect(
                    self.open_band_preview_dialog)
            if hasattr(self.dialog, 'openHistogramButton'):
                self.dialog.openHistogramButton.setVisible(False)
            if hasattr(self.dialog, 'nextToSieve'):
                self.dialog.nextToSieve.clicked.connect(self.next_to_sieve)

            for i in range(1, self.dialog.tabWidget.count()):
                self.dialog.tabWidget.setTabEnabled(i, False)

            self.populate_project_layers()

        # sempre mostra a janela no final
        self.dialog.show()

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
            "9. Centroids & Export:\n"
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
        if hasattr(self.dialog, 'previewVectors'):
            self.dialog.previewVectors.clicked.connect(
                self.open_vectors_preview)
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
                "⚠️ Nenhum botão 'Preview' encontrado no UI — verifique o objectName no main.ui")

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
        if hasattr(self.dialog, 'nextToCentroids'):
            self.dialog.nextToCentroids.clicked.connect(self.next_to_centroids)

        if hasattr(self.dialog, 'generate_centroids'):
            self.dialog.generate_centroids.clicked.connect(
                self.generate_centroids)
        if hasattr(self.dialog, 'export_all'):
            self.dialog.export_all.clicked.connect(self.export_all_results)
        if hasattr(self.dialog, 'resetButton'):
            self.dialog.resetButton.clicked.connect(self.reset_plugin_state)

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

        QgsProject.instance().addMapLayer(layer)
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
            layout.addWidget(canvas)

            # Min Year 1 - Label, Slider e SpinBox
            min1_label = QLabel("Min Year 1:")
            min1_slider = QSlider(Qt.Horizontal)
            min1_slider.setRange(0, 255)
            min1_slider.setValue(int(np.nanmin(band1))
                                 if not np.all(np.isnan(band1)) else 0)
            min1_spinbox = QSpinBox()
            min1_spinbox.setRange(0, 255)
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
            max1_slider.setRange(0, 255)
            max1_slider.setValue(int(np.nanmax(band1))
                                 if not np.all(np.isnan(band1)) else 255)
            max1_spinbox = QSpinBox()
            max1_spinbox.setRange(0, 255)
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
            min2_slider.setRange(0, 255)
            min2_slider.setValue(int(np.nanmin(band2))
                                 if not np.all(np.isnan(band2)) else 0)
            min2_spinbox = QSpinBox()
            min2_spinbox.setRange(0, 255)
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
            max2_slider.setRange(0, 255)
            max2_slider.setValue(int(np.nanmax(band2))
                                 if not np.all(np.isnan(band2)) else 255)
            max2_spinbox = QSpinBox()
            max2_spinbox.setRange(0, 255)
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
        if not self.norm_year1_path or not self.norm_year2_path:
            QMessageBox.warning(self.dialog, "Warning",
                                "Please normalize contrast first.")
            return
        try:
            output_dir = os.path.join(self.temp_dir, "binarized_images")
            os.makedirs(output_dir, exist_ok=True)
            self.bin_year1_path = os.path.join(output_dir, "bin_year1.tif")
            self.bin_year2_path = os.path.join(output_dir, "bin_year2.tif")

            ds1 = gdal.Open(self.norm_year1_path)
            if ds1 is None:
                raise Exception(
                    f"Failed to open normalized image for Year 1: {self.norm_year1_path}")
            data1 = ds1.ReadAsArray()
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

            ds2 = gdal.Open(self.norm_year2_path)
            if ds2 is None:
                raise Exception(
                    f"Failed to open normalized image for Year 2: {self.norm_year2_path}")
            data2 = ds2.ReadAsArray()
            bin_data2 = (data2 > self.dialog.spinThresholdYear2.value()).astype(
                np.uint8) * 255
            out_ds2 = driver.Create(
                self.bin_year2_path, ds2.RasterXSize, ds2.RasterYSize, 1, gdal.GDT_Byte)
            out_ds2.SetGeoTransform(ds2.GetGeoTransform())
            out_ds2.SetProjection(ds2.GetProjection())
            out_ds2.GetRasterBand(1).WriteArray(bin_data2)
            out_ds2 = None
            ds2 = None

            if os.path.exists(self.bin_year1_path) and QgsRasterLayer(self.bin_year1_path, "").isValid():
                self._load_to_project(
                    self.bin_year1_path, "Binarized - Year 1")
            else:
                raise Exception("Failed to create binarized image for Year 1.")
            if os.path.exists(self.bin_year2_path) and QgsRasterLayer(self.bin_year2_path, "").isValid():
                self._load_to_project(
                    self.bin_year2_path, "Binarized - Year 2")
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
                self.log_message("Tentando OTB MultivariateAlterationDetector")
                processing.run("otb:MultivariateAlterationDetector", {
                    'in1': year1_path,
                    'in2': year2_path,
                    'out': self.difference_path,
                    'outputpixeltype': 2
                })
            except Exception as e_otb:
                self.log_message(
                    f"OTB falhou: {str(e_otb)}. Revertendo para diferença simples.")
                ds1 = gdal.Open(year1_path)
                ds2 = gdal.Open(year2_path)
                if ds1 is None or ds2 is None:
                    self.log_message(
                        f"Falha ao abrir imagens: Year1={year1_path}, Year2={year2_path}")
                    return
                arr1 = ds1.GetRasterBand(1).ReadAsArray().astype(np.float32)
                arr2 = ds2.GetRasterBand(1).ReadAsArray().astype(np.float32)
                if arr1.shape != arr2.shape:
                    self.log_message("Imagens com dimensões diferentes.")
                    return
                ds1 = None
                ds2 = None
                diff_arr = (arr2 - arr1).astype(np.float32)
                driver = gdal.GetDriverByName('GTiff')
                out = driver.Create(
                    self.difference_path, diff_arr.shape[1], diff_arr.shape[0], 1, gdal.GDT_Float32)
                if out is None:
                    self.log_message(
                        f"Falha ao criar output: {self.difference_path}")
                    return
                out.SetGeoTransform(gdal.Open(year1_path).GetGeoTransform())
                out.SetProjection(gdal.Open(year1_path).GetProjection())
                out.GetRasterBand(1).WriteArray(diff_arr)
                out = None
                self.log_message("Fallback GDAL completado.")

            if os.path.exists(self.difference_path) and QgsRasterLayer(self.difference_path, "").isValid():
                self._load_to_project(self.difference_path, "Difference Image")
                self.log_message("Successfully calculated difference.")
                QMessageBox.information(
                    self.dialog, "Sucess", "Successfully calculated difference.")
            else:
                raise Exception("Failed to create difference image.")

        except Exception as e:
            self.log_message(f"Erro no cálculo da diferença: {str(e)}")
            QMessageBox.warning(self.dialog, "Erro",
                                f"Erro ao calcular a diferença: {str(e)}")
            return

    def next_to_gain_loss(self):
        if self.difference_path and os.path.exists(self.difference_path):
            tab_index = 6  # Índice da aba Gain & Loss Masks
            self.dialog.tabWidget.setTabEnabled(tab_index, True)
            self.dialog.tabWidget.setCurrentIndex(tab_index)
            self.log_message("Navegado para a aba Gain & Loss Masks.")
        else:
            QMessageBox.warning(
                self.dialog, "Aviso", "Por favor, calcule a imagem de diferença primeiro.")

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
        thresh_gain_spin = QDoubleSpinBox()
        thresh_gain_spin.setDecimals(2)
        thresh_gain_spin.setRange(-255.0, 255.0)
        thresh_gain_spin.setSingleStep(0.10)
        thresh_gain_spin.setValue(0.10)
        layout.addWidget(QLabel("Gain Threshold:"))
        layout.addWidget(thresh_gain_spin)

        # Loss threshold
        thresh_loss_spin = QDoubleSpinBox()
        thresh_loss_spin.setDecimals(2)
        thresh_loss_spin.setRange(-255.0, 255.0)
        thresh_loss_spin.setSingleStep(0.10)
        thresh_loss_spin.setValue(-0.10)
        layout.addWidget(QLabel("Loss Threshold:"))
        layout.addWidget(thresh_loss_spin)

        # Sieve threshold for cleaning isolated pixels
        layout.addWidget(QLabel("\nSieve Settings (for cleaning masks):"))
        sieve_threshold_spin = QSpinBox()
        sieve_threshold_spin.setRange(1, 1000)
        sieve_threshold_spin.setValue(8)
        sieve_threshold_spin.setToolTip("Minimum number of connected pixels to keep. Smaller groups will be removed.")
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
        apply_sieve_button.setToolTip("Remove small isolated pixel groups from the generated masks")

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

            # Generate masks
            gain = np.where(diff > thresh_gain, 0, 255).astype(
                np.uint8)   # black = gain
            loss = np.where(diff < thresh_loss, 255, 0).astype(
                np.uint8)   # white = loss

            driver = gdal.GetDriverByName('GTiff')
            out_g = driver.Create(
                self.gain_mask_path, gain.shape[1], gain.shape[0], 1, gdal.GDT_Byte)
            out_g.SetGeoTransform(geo)
            out_g.SetProjection(proj)
            out_g.GetRasterBand(1).WriteArray(gain)
            out_g.FlushCache()
            out_g = None

            out_l = driver.Create(
                self.loss_mask_path, loss.shape[1], loss.shape[0], 1, gdal.GDT_Byte)
            out_l.SetGeoTransform(geo)
            out_l.SetProjection(proj)
            out_l.GetRasterBand(1).WriteArray(loss)
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
            QMessageBox.warning(self.dialog, "Aviso",
                                "Gere as máscaras de ganho/perda primeiro.")

    def on_generate_gain_loss_clicked(self):
        """Slot connected to the button in the UI. Opens the Gain/Loss settings dialog."""
        self.show_gain_loss_dialog()

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
            QMessageBox.warning(self.dialog, "Aviso",
                                "Gere as máscaras de ganho/perda primeiro.")
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
                })
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
                })
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
        QgsProject.instance().addMapLayer(layer)
        self.loaded_layer_ids.append(layer.id())
        self.log_message(f"Vector layer loaded: {name}")
        return layer

    def open_vectors_preview(self):
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

        simplify_tolerance_slider = QSlider(Qt.Horizontal)
        simplify_tolerance_slider.setRange(0, 10)
        simplify_tolerance_slider.setValue(2)
        simplify_label = QLabel(
            f"Simplification Tolerance: {simplify_tolerance_slider.value()}")
        simplify_tolerance_slider.valueChanged.connect(
            lambda val: simplify_label.setText(f"Simplification Tolerance: {val}"))
        layout.addWidget(QLabel("Tolerance for Simplification:"))
        layout.addWidget(QLabel(
            "Higher value: more simplification (less details); Lower value: less simplification (more details)"))
        layout.addWidget(simplify_tolerance_slider)
        layout.addWidget(simplify_label)

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

        def update_preview():
            labeled_gain, num_gain = ndi.label(arr_bin_gain)
            filtered_gain = np.zeros_like(arr_bin_gain)
            for i in range(1, num_gain + 1):
                component = (labeled_gain == i)
                coords = np.argwhere(component)
                area = coords.shape[0]
                if area < min_area_slider.value():
                    continue
                min_y, min_x = coords.min(0)
                max_y, max_x = coords.max(0)
                width = max_x - min_x + 1
                height = max_y - min_y + 1
                perimeter = 2 * (width + height)
                compacidade = 4 * np.pi * area / \
                    (perimeter ** 2) if perimeter > 0 else 0
                if compacidade < min_compact_slider.value() / 100:
                    continue
                filtered_gain[component] = 1
            ax_gain.clear()
            ax_gain.imshow(filtered_gain, cmap='gray')
            ax_gain.set_title('Preview Gain Mask', fontsize=10)
            canvas_gain.draw()

            labeled_loss, num_loss = ndi.label(arr_bin_loss)
            filtered_loss = np.zeros_like(arr_bin_loss)
            for i in range(1, num_loss + 1):
                component = (labeled_loss == i)
                coords = np.argwhere(component)
                area = coords.shape[0]
                if area < min_area_slider.value():
                    continue
                min_y, min_x = coords.min(0)
                max_y, max_x = coords.max(0)
                width = max_x - min_x + 1
                height = max_y - min_y + 1
                perimeter = 2 * (width + height)
                compacidade = 4 * np.pi * area / \
                    (perimeter ** 2) if perimeter > 0 else 0
                if compacidade < min_compact_slider.value() / 100:
                    continue
                filtered_loss[component] = 1
            ax_loss.clear()
            ax_loss.imshow(filtered_loss, cmap='gray')
            ax_loss.set_title('Preview Loss Mask', fontsize=10)
            canvas_loss.draw()

        min_area_slider.valueChanged.connect(update_preview)
        min_compact_slider.valueChanged.connect(update_preview)
        simplify_tolerance_slider.valueChanged.connect
        ortho_tolerance_slider.valueChanged.connect(update_preview)

        def apply_vectorization():
            simplify_tol = simplify_tolerance_slider.value()
            ortho_tol = ortho_tolerance_slider.value() / 2.0
            min_area = min_area_slider.value()
            min_compact = min_compact_slider.value() / 100

            ds_gain_full = gdal.Open(self.gain_mask_path)
            ds_loss_full = gdal.Open(self.loss_mask_path)
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

            # Definir caminhos finais para os vetores ortogonalizados
            self.ortho_gain_path = os.path.join(
                self.temp_dir, "preview_gain_vector_ortho.shp")
            self.ortho_loss_path = os.path.join(
                self.temp_dir, "preview_loss_vector_ortho.shp")

            # Ortho para GAIN
            self._orthogonalize_vector(
                self.gain_vector_path, self.ortho_gain_path, simplify_tol, ortho_tol
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

            # Ortho para LOSS
            self._orthogonalize_vector(
                loss_vector_raw, self.ortho_loss_path, simplify_tol, ortho_tol
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

    def _orthogonalize_vector(self, input_path, output_path, simplify_tol, ortho_tol):
        layer = QgsVectorLayer(input_path, "temp", "ogr")
        fields = layer.fields()
        writer = QgsVectorFileWriter(
            output_path, 'UTF-8', fields, QgsWkbTypes.Polygon, layer.crs(), 'ESRI Shapefile')
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            simplified = geom.simplify(simplify_tol)
            orthogonal = simplified.densifyByCount(5).orthogonalize(
                ortho_tol) if hasattr(simplified, 'orthogonalize') else simplified
            feat.setGeometry(orthogonal)
            writer.addFeature(feat)
        del writer

        self._load_vector_to_project(self.gain_vector_path, "Gain Vectors")
        self._load_vector_to_project(self.loss_vector_path, "Loss Vectors")

        # agora sim os combos podem ser atualizados
        # self.populate_vector_combos()

    def reproject_gain_loss_to_utm(self):
        """Reprojeta os vetores de ganho/perda para UTM e salva shapefiles."""
        try:
            if not self.gain_vector_path or not self.loss_vector_path:
                QMessageBox.warning(
                    self.dialog, "Aviso", "Vectorize primeiro as máscaras de ganho/perda.")
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
                self.dialog, "Sucesso", "Vetores reprojetados para UTM e carregados no projeto.")

        except Exception as e:
            QMessageBox.warning(self.dialog, "Erro",
                                f"Erro ao reprojetar vetores: {str(e)}")

    def next_to_metrics(self):
        """Abre a aba Metrics carregando diretamente os vetores UTM exportados."""
        if not hasattr(self, 'gain_vector_utm_path') or not os.path.exists(self.gain_vector_utm_path):
            QMessageBox.warning(
                self.dialog, "Aviso", "Reprojete os vetores primeiro na aba Vectorize.")
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

        # Habilita aba Metrics
        tab_index = 8  # índice da aba Metrics (ajuste conforme sua UI)
        self.dialog.tabWidget.setTabEnabled(tab_index, True)
        self.dialog.tabWidget.setCurrentIndex(tab_index)

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
                QMessageBox.warning(self.dialog, "Erro",
                                    f"Falha ao carregar camada {layer.name()}")
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
                self.dialog, "Aviso", "Reprojete os vetores primeiro na aba Vectorize.")
            return

        self.gain_layer = self.ensure_fields(
            self.gain_vector_utm_path, "Gain Vector UTM")
        if self.gain_layer:
            QgsProject.instance().addMapLayer(self.gain_layer)
            self.log_message(
                "Gain Vector UTM carregado via load_gain_vector (compatibilidade).")

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
                "Loss Vector UTM carregado via load_loss_vector (compatibilidade).")

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

        # Corrige geometrias e converte para singlepart (mantém)
        fixed_path = os.path.join(
            self.temp_dir, f"fixed_{layer_name.lower().replace(' ', '_')}.shp")
        processing.run("qgis:fixgeometries", {
                       'INPUT': layer, 'OUTPUT': fixed_path})
        fixed_layer = QgsVectorLayer(fixed_path, "Fixed Layer", "ogr")
        if not fixed_layer.isValid():
            raise Exception(f"Failed to fix geometries for {layer_name}")

        single_path = os.path.join(
            self.temp_dir, f"single_{layer_name.lower().replace(' ', '_')}.shp")
        processing.run("qgis:multiparttosingleparts", {
                       'INPUT': fixed_layer, 'OUTPUT': single_path})
        layer = QgsVectorLayer(single_path, layer_name, "ogr")
        if not layer.isValid():
            raise Exception(
                f"Failed to convert to singlepart for {layer_name}")

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

            # Substitua as linhas problemáticas por este bloco seguro:
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

            # Para Gain
            if gain_layers and len(gain_layers) > 0:
                gain_layer = gain_layers[0]
                expression = expression_base + ' AND "val" = 255'
                gain_layer.removeSelection()
                gain_layer.selectByExpression(expression)
                self.log_message(
                    f"Test expression: {expression} — Expecting ~{gain_layer.featureCount() / 2} features")
                after_select = gain_layer.selectedFeatureCount()
                self.log_message(f"Selected: {after_select} features")
                if after_select == 0:
                    # Fallback: selecione só válidas
                    gain_layer.selectByExpression(
                        '"is_valid" = 1 AND "val" = 255')
                    self.log_message("Fallback: All valid selected")
                self.iface.layerTreeView().refreshLayerSymbology(gain_layer.id())

            # Para Loss (repete o padrão)
            if loss_layers and len(loss_layers) > 0:
                loss_layer = loss_layers[0]
                expression = expression_base + ' AND "val" = 0'
                loss_layer.removeSelection()
                loss_layer.selectByExpression(expression)
                self.log_message(
                    f"Test expression: {expression} — Expecting ~{loss_layer.featureCount() / 2} features")
                after_select = loss_layer.selectedFeatureCount()
                self.log_message(f"Selected: {after_select} features")
                if after_select == 0:
                    # Fallback: selecione só válidas
                    loss_layer.selectByExpression(
                        '"is_valid" = 1 AND "val" = 0')
                    self.log_message("Fallback: All valid selected")
                self.iface.layerTreeView().refreshLayerSymbology(loss_layer.id())

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
        dlg = QDialog(self.dialog)
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

            # Sincronização bidirecional
            sld.valueChanged.connect(lambda val: spn.setValue(val / scale))
            spn.valueChanged.connect(
                lambda val: sld.setValue(int(val * scale)))

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
        slider_area_g.valueChanged.connect(lambda v: spin_area_g.setValue(v))
        spin_area_g.valueChanged.connect(
            lambda v: slider_area_g.setValue(int(v)))

        slider_per_g.valueChanged.connect(lambda v: spin_per_g.setValue(v))
        spin_per_g.valueChanged.connect(
            lambda v: slider_per_g.setValue(int(v)))

        slider_el_g.valueChanged.connect(
            lambda v: spin_el_g.setValue(v / 10.0))
        spin_el_g.valueChanged.connect(
            lambda v: slider_el_g.setValue(int(v * 10)))

        slider_rec_g.valueChanged.connect(
            lambda v: spin_rec_g.setValue(v / 100.0))
        spin_rec_g.valueChanged.connect(
            lambda v: slider_rec_g.setValue(int(v * 100)))

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
        loss_rec_box, slider_rec_l, spin_rec_l = metric_slider(
            "Min Rectangularity:", 0, 100, 1, decimals=2, scale=100.0)

        for box in [loss_area_box, loss_per_box, loss_elo_box, loss_rec_box]:
            loss_layout.addLayout(box)

        slider_area_l.valueChanged.connect(lambda v: spin_area_l.setValue(v))
        spin_area_l.valueChanged.connect(
            lambda v: slider_area_l.setValue(int(v)))

        slider_per_l.valueChanged.connect(lambda v: spin_per_l.setValue(v))
        spin_per_l.valueChanged.connect(
            lambda v: slider_per_l.setValue(int(v)))

        slider_el_l.valueChanged.connect(
            lambda v: spin_el_l.setValue(v / 10.0))
        spin_el_l.valueChanged.connect(
            lambda v: slider_el_l.setValue(int(v * 10)))

        slider_rec_l.valueChanged.connect(
            lambda v: spin_rec_l.setValue(v / 100.0))
        spin_rec_l.valueChanged.connect(
            lambda v: slider_rec_l.setValue(int(v * 100)))

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
            simple_expr = f'"is_valid" = 1 AND "val" = {255 if is_gain else 0}'
            layer.selectByExpression(simple_expr)
            simple_sel = layer.selectedFeatureCount()
            self.log_message(
                f"🔍 Simple test (is_valid=1 AND val={255 if is_gain else 0}): {simple_sel} selected")
            layer.removeSelection()  # Limpa pra filtro completo

            try:
                # lê valores conforme tipo
                min_a = slider_area_g.value() if is_gain else slider_area_l.value()
                min_p = slider_per_g.value() if is_gain else slider_per_l.value()
                max_e = (slider_el_g.value()
                         if is_gain else slider_el_l.value()) / 10.0
                min_r = (slider_rec_g.value()
                         if is_gain else slider_rec_l.value()) / 100.0
                val_condition = 255 if is_gain else 0

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
        result = dlg.exec_()  # ← MUDANÇA: Captura o result
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
            loss_layer.selectByExpression(expression_base + ' AND "val" = 0')

    def export_from_preview(self, gain_layer, loss_layer):
        """Export direto da seleção no preview dialog."""
        export_dir = QFileDialog.getExistingDirectory(
            self.dialog, "Export Filtered Selection")
        if export_dir:
            if gain_layer.selectedFeatureCount() > 0:
                processing.run("native:saveselectedfeatures", {
                               'INPUT': gain_layer, 'OUTPUT': os.path.join(export_dir, "preview_gain.shp")})
            if loss_layer.selectedFeatureCount() > 0:
                processing.run("native:saveselectedfeatures", {
                               'INPUT': loss_layer, 'OUTPUT': os.path.join(export_dir, "preview_loss.shp")})
            QMessageBox.information(
                self.dialog, "Success", f"Exported to {export_dir}")

    def export_filtered_vectors(self):
        """Exporta as features selecionadas (filtradas) para um shapefile."""
        export_dir = QFileDialog.getExistingDirectory(
            self.dialog, "Select Output Directory for Filtered Vectors")
        if not export_dir:
            return

        try:
            gain_layers = QgsProject.instance().mapLayersByName("Gain Vectors (with Metrics)")
            loss_layers = QgsProject.instance().mapLayersByName("Loss Vectors (with Metrics)")

            gain_output_path = None
            loss_output_path = None

            # Exporta Gain Vectors selecionados (com filtro is_valid)
            if gain_layers and len(gain_layers) > 0:
                gain_layer = gain_layers[0]
                # Seleciona só válidas antes de export (evita ruído)
                if gain_layer.selectedFeatureCount() == 0:
                    gain_layer.selectByExpression(
                        '"is_valid" = 1 AND "val" = 255')
                gain_output_path = os.path.join(
                    export_dir, "filtered_gain_vectors.shp")
                params = {
                    'INPUT': gain_layer,
                    'OUTPUT': gain_output_path
                }
                result = processing.run("native:saveselectedfeatures", params)
                self.log_message(
                    f"Filtered Gain Vectors exported to {gain_output_path} ({gain_layer.selectedFeatureCount()} features)")
                QMessageBox.information(
                    self.dialog, "Success", f"Filtered Gain Vectors exported to {gain_output_path}")

            # Exporta Loss Vectors selecionados (com filtro is_valid)
            if loss_layers and len(loss_layers) > 0:
                loss_layer = loss_layers[0]
                if loss_layer.selectedFeatureCount() == 0:
                    loss_layer.selectByExpression(
                        '"is_valid" = 1 AND "val" = 0')
                loss_output_path = os.path.join(
                    export_dir, "filtered_loss_vectors.shp")
                params = {
                    'INPUT': loss_layer,
                    'OUTPUT': loss_output_path
                }
                result = processing.run("native:saveselectedfeatures", params)
                self.log_message(
                    f"Filtered Loss Vectors exported to {loss_output_path} ({loss_layer.selectedFeatureCount()} features)")
                QMessageBox.information(
                    self.dialog, "Success", f"Filtered Loss Vectors exported to {loss_output_path}")

            self.filtered_gain_vector = gain_output_path
            self.filtered_loss_vector = loss_output_path

        except Exception as e:
            self.log_message(f"Error exporting filtered vectors: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error exporting filtered vectors: {str(e)}")

    def next_to_centroids(self):
        """Avança para o tab de centroids (sem calcular nada automaticamente)."""
        try:
            # Pega o atual (deve ser 8 pra Metrics)
            current_index = self.dialog.tabWidget.currentIndex()
            next_index = current_index + 1  # Próximo (9 pra Centroids)
            # ← FIX: Habilita o tab (e seus botões filhos)
            self.dialog.tabWidget.setTabEnabled(next_index, True)
            self.dialog.tabWidget.setCurrentIndex(next_index)  # Avança
            self.log_message(
                f"➡️ Advanced from tab {current_index} to {next_index} (Centroids). Buttons now enabled.")
        except Exception as e:
            self.log_message(f"Error advancing to centroids tab: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error advancing: {str(e)}")

    def generate_centroids(self):
        """Gera os centroides de TODAS as features nas layers filtradas (Filtered Gain/Loss) usando o algoritmo nativo do QGIS."""
        try:
            # Busca layers FILTRADAS (depois do export)
            gain_layers = QgsProject.instance().mapLayersByName("Filtered Gain")
            loss_layers = QgsProject.instance().mapLayersByName("Filtered Loss")

            if not (gain_layers or loss_layers):
                QMessageBox.warning(
                    self.dialog, "Warning", "No filtered layers available (Filtered Gain/Loss). Run 'Preview Filtered Vectors' > 'Export Selection' first.")
                self.log_message(
                    "No filtered layers found — run export before centroids.")
                return

            centroids_generated = False

            # Processa Filtered Gain (TODAS as features)
            if gain_layers and len(gain_layers) > 0:
                gain_layer = gain_layers[0]
                if gain_layer.featureCount() > 0:
                    centroid_path = os.path.join(
                        self.temp_dir, "filtered_gain_centroids.shp")
                    params = {
                        'INPUT': gain_layer,
                        'ALL_PARTS': False,  # Padrão para centroides simples
                        'OUTPUT': centroid_path
                    }
                    result = processing.run("native:centroids", params)
                    if 'OUTPUT' in result:
                        centroid_layer = QgsVectorLayer(
                            result['OUTPUT'], "Filtered Gain Centroids", "ogr")
                        if centroid_layer.isValid():
                            QgsProject.instance().addMapLayer(centroid_layer)
                            self.log_message(
                                f"✅ Centroids generated for Filtered Gain ({centroid_layer.featureCount()} points) and loaded in project.")
                            centroids_generated = True
                        else:
                            self.log_message(
                                "Warning: Invalid centroid layer for Filtered Gain.")
                    else:
                        self.log_message(
                            "Error: No output from centroids algorithm for Filtered Gain.")
            else:
                self.log_message("Filtered Gain layer has no features.")

            # Processa Filtered Loss (TODAS as features)
            if loss_layers and len(loss_layers) > 0:
                loss_layer = loss_layers[0]
                if loss_layer.featureCount() > 0:
                    centroid_path = os.path.join(
                        self.temp_dir, "filtered_loss_centroids.shp")
                    params = {
                        'INPUT': loss_layer,
                        'ALL_PARTS': False,  # Padrão para centroides simples
                        'OUTPUT': centroid_path
                    }
                    result = processing.run("native:centroids", params)
                    if 'OUTPUT' in result:
                        centroid_layer = QgsVectorLayer(
                            result['OUTPUT'], "Filtered Loss Centroids", "ogr")
                        if centroid_layer.isValid():
                            QgsProject.instance().addMapLayer(centroid_layer)
                            self.log_message(
                                f"✅ Centroids generated for Filtered Loss ({centroid_layer.featureCount()} points) and loaded in project.")
                            centroids_generated = True
                        else:
                            self.log_message(
                                "Warning: Invalid centroid layer for Filtered Loss.")
                    else:
                        self.log_message(
                            "Error: No output from centroids algorithm for Filtered Loss.")
                else:
                    self.log_message("Filtered Loss layer has no features.")

            if centroids_generated:
                self.log_message(
                    "Centroid generation completed from all filtered features. Proceed to clustering/export.")
                QMessageBox.information(
                    self.dialog, "Success", f"Centroids generated from filtered layers. Check project layers (e.g., Filtered Gain Centroids).")
            else:
                self.log_message(
                    "No centroids generated — filtered layers empty.")

        except Exception as e:
            self.log_message(f"Error generating centroids: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error generating centroids: {str(e)}")

    def generate_heatmaps(self):
        """Gera heatmaps opcionais a partir dos centroids de Filtered Gain/Loss, com escolha do usuário."""
        try:
            # Busca layers de centroids
            gain_centroids_layers = QgsProject.instance(
            ).mapLayersByName("Filtered Gain Centroids")
            loss_centroids_layers = QgsProject.instance(
            ).mapLayersByName("Filtered Loss Centroids")

            if not (gain_centroids_layers or loss_centroids_layers):
                QMessageBox.warning(self.dialog, "Warning",
                                    "No centroid layers available (Filtered Gain/Loss Centroids). Generate centroids first.")
                self.log_message(
                    "No centroid layers found — generate centroids before heatmaps.")
                return

            # Dialog para escolha (Gain, Loss ou Both)
            choice_dlg = QDialog(self.dialog)
            choice_dlg.setWindowTitle("Generate Heatmaps")
            choice_layout = QVBoxLayout(choice_dlg)

            group_box = QGroupBox("Select which heatmaps to generate:")
            group_layout = QVBoxLayout(group_box)
            radio_gain = QRadioButton("Gain Centroids Only")
            radio_loss = QRadioButton("Loss Centroids Only")
            radio_both = QRadioButton("Both Gain and Loss")
            radio_both.setChecked(True)  # Default: Both
            group_layout.addWidget(radio_gain)
            group_layout.addWidget(radio_loss)
            group_layout.addWidget(radio_both)
            choice_layout.addWidget(group_box)

            # Slider para Radius (opcional, default 1000m)
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
            ok_btn = QPushButton("Generate")
            cancel_btn = QPushButton("Cancel")
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            choice_layout.addLayout(btn_layout)

            def generate_selected():
                radius = radius_spin.value()
                heatmaps_generated = False

                # Processa Gain se selecionado
                if radio_gain.isChecked() or radio_both.isChecked():
                    if gain_centroids_layers:
                        gain_centroids = gain_centroids_layers[0]
                        if gain_centroids.featureCount() > 0:
                            heatmap_path = os.path.join(
                                self.temp_dir, "gain_heatmap.tif")
                            params = {
                                'INPUT': gain_centroids,
                                'RADIUS': radius,
                                'PIXEL_SIZE': 10,  # Ajuste para resolução desejada
                                'KERNEL': 0,  # Quartic (default)
                                'OUTPUT': heatmap_path
                            }
                            # processamento: use .get to be resilient ao formato de retorno
                            result = processing.run(
                                "qgis:heatmapkerneldensityestimation", params)
                            out_path = result.get('OUTPUT') or result.get(
                                'OUTPUT_RASTER') or result.get('OUTPUT_LAYER')
                            if out_path:
                                heatmap_layer = QgsRasterLayer(
                                    out_path, "Gain Heatmap")
                                if heatmap_layer.isValid():
                                    QgsProject.instance().addMapLayer(heatmap_layer)
                                    self.log_message(
                                        f"✅ Gain Heatmap generated ({radius}m radius) and loaded in project.")
                                    heatmaps_generated = True
                                else:
                                    self.log_message(
                                        "Warning: Invalid Gain Heatmap layer.")
                        else:
                            self.log_message(
                                "Filtered Gain Centroids has no features.")

                # Processa Loss se selecionado
                if radio_loss.isChecked() or radio_both.isChecked():
                    if loss_centroids_layers:
                        loss_centroids = loss_centroids_layers[0]
                        if loss_centroids.featureCount() > 0:
                            heatmap_path = os.path.join(
                                self.temp_dir, "loss_heatmap.tif")
                            params = {
                                'INPUT': loss_centroids,
                                'RADIUS': radius,
                                'PIXEL_SIZE': 10,  # Ajuste para resolução desejada
                                'KERNEL': 0,  # Quartic (default)
                                'OUTPUT': heatmap_path
                            }
                            result = processing.run(
                                "qgis:heatmapkerneldensityestimation", params)
                            out_path = result.get('OUTPUT') or result.get(
                                'OUTPUT_RASTER') or result.get('OUTPUT_LAYER')
                            if out_path:
                                heatmap_layer = QgsRasterLayer(
                                    out_path, "Loss Heatmap")
                                if heatmap_layer.isValid():
                                    QgsProject.instance().addMapLayer(heatmap_layer)
                                    self.log_message(
                                        f"✅ Loss Heatmap generated ({radius}m radius) and loaded in project.")
                                    heatmaps_generated = True
                                else:
                                    self.log_message(
                                        "Warning: Invalid Loss Heatmap layer.")
                        else:
                            self.log_message(
                                "Filtered Loss Centroids has no features.")

                if heatmaps_generated:
                    QMessageBox.information(
                        self.dialog, "Success", "Heatmaps generated and loaded. They will be included in Export All if in temp dir.")
                else:
                    self.log_message(
                        "No heatmaps generated — no centroid features available.")
                choice_dlg.accept()

            ok_btn.clicked.connect(generate_selected)
            cancel_btn.clicked.connect(choice_dlg.reject)

            choice_dlg.exec_()

        except Exception as e:
            self.log_message(f"Error generating heatmaps: {str(e)}")
            QMessageBox.warning(self.dialog, "Error",
                                f"Error generating heatmaps: {str(e)}")

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
