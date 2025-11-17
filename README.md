English:
Urban Change Aid - QGIS Plugin for Urban Change Detection

Urban Change Aid is a powerful, semi-automated QGIS plugin designed to transform satellite imagery analysis into concrete insights into the expansion, emergence, or suppression of urban constructions.

Identify changes in minutes using remote sensing techniques such as normalization, binarization, geometric filters, and heat maps. Export vectorized results ready for any spatial analysis.

💡 The Problem: Manual Urban Change Detection is a Nightmare

• Subjective and Time-consuming: Manual analysis of irregular constructions is exhaustive. Subtracting bands from satellite imagery generates excessive noise (dirt roads, shadows, seasonal variations).

• No Objective Metrics: Quantification is subjective and ignores critical metrics such as size, shape, and actual expansion patterns.

• Excessive Noise: Raw change detection captures everything: changes in vegetation, shadows, and sensor artifacts. Separating real changes from noise requires extensive manual cleaning.

• Limited Spatial Analysis: Without vectorized outputs and geometric metrics, it's impossible to query specific areas, calculate accurate statistics, or identify zones of urban sprawl concentration.

✅ The Solution: A Semi-Automated Workflow that Transforms Data into Insights

Urban Change Aid uses remote sensing techniques to automate filtering, calculate objective metrics, and generate vectorized results, reducing hours of manual work to minutes.

• Objective Metrics: Automatically calculate area, perimeter, elongation, and other geometric properties. Filter buildings by size and shape to focus on relevant changes.

• Time Efficiency: What used to take hours now takes minutes. Semi-automated filtering removes most of the noise, leaving only final cleaning, saving time and reducing errors.

• Vectorized Output: Export GIS-ready polygon layers with centroids and heat maps. Query, analyze, and visualize urban changes with standard spatial analysis tools. ⚙️ How Urban Change Aid Works: 10-Step Workflow

The plugin guides you through a 10-step workflow that transforms raw satellite imagery into actionable urban intelligence:

1. Input Data (T1 and T2): Load georeferenced satellite imagery or photos from two different time periods.

2. Normalization: Standardize pixel values ​​between the two images to ensure comparable data.

3. Binarization: Convert the normalized images to binary format (building/non-building) to distinguish built structures.

4. Change Detection (T2 - T1): Subtract T1 from T2. Positive values ​​= Gain (new construction, in Cyan), Negative values ​​= Loss (demolished structures, in Red).

5. Geometric Metric Filters: Remove false positives using geometric properties: area (size), perimeter, elongation (form factor), and rectangularity.

6. Vectorization: Transform filtered raster results into vector polygons (Filtered Gain and Filtered Loss).

7. Centroid Calculation: Calculate the geometric center of each gain and loss polygon for point representation.

8. Heat Map Generation: Generate heat maps from gain centroids to visualize areas of new development concentration.

9. Metric-Based Selection: Query and filter construction polygons based on geometric metrics to focus analysis on specific types or size ranges.

10. Export and Analysis: Export vectorized results in standard GIS formats for reporting, statistics, and integration with other workflows.

🎯 For Land Enforcement and Control Agencies

A powerful tool for rapid monitoring and data-driven decision-making.

• Rapid Monitoring: Quickly monitor urban expansions, protected areas, and risk zones. Identify unauthorized construction and track development patterns across large territories in minutes.

• Objective Vectorized Data: Provides objective and measurable data in standard GIS formats. Support enforcement priorities and legal actions with quantifiable evidence.

• Optimized Fieldwork: Focus field inspections on confirmed changes with precise locations. Reduce unnecessary visits and allocate resources efficiently.

• Semi-Automated Efficiency: Works with satellites or georeferenced Google photos. While it doesn't filter out 100% of the noise, it saves hours on final cleanup, balancing automation with expert validation.

🛠️ Installation Guide

Follow these steps to install and configure Urban Change Aid in QGIS.

1. Install QGIS: Download and install QGIS version 3.40 LTR (Long Term Release) from the official website.

2. Install Orfeo Toolbox (OTB): Download OTB for your operating system and extract it to an easily accessible directory, for example, C:/otb910.

3. Install the Plugin: Extract the plugin's ZIP file to the QGIS plugin directory: C:\Users\your_username\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\urban_change_aid

4. Configure OTB in QGIS: In QGIS, go to Options → Processing → Providers → OTB and configure:

• OTB application folder: C:/otb910/lib/otb/applications

• OTB folder: C:/otb910

5. Load the Plugin: Install the Plugin Reloader from the QGIS plugin repository and use it to reload Urban Change Aid. If successful, the plugin will appear in the Plugins menu.

🚀 Ready to Transform Your Urban Analysis?

Download Urban Change Aid and start detecting urban changes with targeted, metrics-driven workflows.

Technical Specification Details Version QGIS 3.40 LTR onwards License GNU GPL v3 Language Python 
[[Link to GitHub]](https://github.com/mikadishen/urban_change_aid/)
[[Link to WebSite]](https://urbanchang-gb98hazp.manus.space)
-------------------
Portuguese: (PT-BR)
Urban Change Aid - Plugin QGIS para Detecção de Mudanças Urbanas

O Urban Change Aid é um plugin QGIS poderoso e semi-automatizado, projetado para transformar a análise de imagens de satélite em insights concretos sobre a expansão, emergência ou supressão de construções urbanas.

Identifique mudanças em minutos usando técnicas de sensoriamento remoto como normalização, binarização, filtros geométricos e mapas de calor. Exporte resultados vetorizados prontos para qualquer análise espacial.


💡 O Problema: Detecção Manual de Mudanças Urbanas é um Pesadelo

• Subjetivo e Demorado: A análise manual de construções irregulares é exaustiva. A subtração de bandas de imagens de satélite gera ruído excessivo (estradas de terra, sombras, variações sazonais).

•Sem Métricas Objetivas: A quantificação é subjetiva e ignora métricas críticas como tamanho, forma e padrões reais de expansão.

•Ruído Excessivo: A detecção de mudança bruta captura tudo: mudanças na vegetação, sombras, e artefatos do sensor. Separar mudanças reais de ruído exige limpeza manual extensa.

•Análise Espacial Limitada: Sem saídas vetorizadas e métricas geométricas, é impossível consultar áreas específicas, calcular estatísticas precisas ou identificar zonas de concentração de expansão urbana.

✅ A Solução: Um Fluxo de Trabalho Semi-Automatizado que Transforma Dados em Insights

O Urban Change Aid utiliza técnicas de sensoriamento remoto para automatizar a filtragem, calcular métricas objetivas e gerar resultados vetorizados, reduzindo horas de trabalho manual a minutos.

•Métricas Objetivas: Calcule automaticamente área, perímetro, alongamento e outras propriedades geométricas. Filtre construções por tamanho e forma para focar em mudanças relevantes.

•Eficiência de Tempo: O que levava horas agora leva minutos. A filtragem semi-automatizada remove a maior parte do ruído, deixando apenas a limpeza final, economizando tempo e reduzindo erros.

•Saída Vetorizada: Exporte camadas de polígonos prontas para GIS com centroides e mapas de calor. Consulte, analise e visualize mudanças urbanas com ferramentas de análise espacial padrão.

⚙️ Como o Urban Change Aid Funciona: Fluxo de Trabalho em 10 Etapas

O plugin guia você através de um fluxo de trabalho de 10 etapas que transforma imagens de satélite brutas em inteligência urbana acionável:

1.Dados de Entrada (T1 e T2): Carregue imagens de satélite ou fotos georreferenciadas de dois períodos de tempo diferentes.

2.Normalização: Padronize os valores de pixel entre as duas imagens para garantir dados comparáveis.

3.Binarização: Converta as imagens normalizadas para o formato binário (construção/não construção) para distinguir estruturas construídas.

4.Detecção de Mudança (T2 - T1): Subtraia T1 de T2. Valores Positivos = Ganho (novas construções, em Ciano), Valores Negativos = Perda (estruturas demolidas, em Vermelho).

5.Filtros de Métrica Geométrica: Remova falsos positivos usando propriedades geométricas: área (tamanho), perímetro, alongamento (fator de forma) e retangularidade.

6.Vetorização: Transforme os resultados raster filtrados em polígonos vetoriais (Ganho Filtrado e Perda Filtrada).

7.Cálculo de Centroides: Calcule o centro geométrico de cada polígono de ganho e perda para representação pontual.

8.Geração de Mapa de Calor: Gere mapas de calor a partir dos centroides de ganho para visualizar áreas de concentração de novo desenvolvimento.

9.Seleção Baseada em Métrica: Consulte e filtre polígonos de construção com base em métricas geométricas para focar a análise em tipos ou faixas de tamanho específicos.

10.Exportação e Análise: Exporte resultados vetorizados em formatos GIS padrão para relatórios, estatísticas e integração com outros fluxos de trabalho.


🎯 Para Agências de Fiscalização e Controle Territorial

Uma ferramenta poderosa para monitoramento rápido e tomada de decisões baseada em dados.

•Monitoramento Rápido: Monitore expansões urbanas, áreas protegidas e zonas de risco rapidamente. Identifique construções não autorizadas e rastreie padrões de desenvolvimento em grandes territórios em minutos.

•Dados Vetorizados Objetivos: Fornece dados objetivos e mensuráveis em formatos GIS padrão. Apoie prioridades de fiscalização e ações legais com evidências quantificáveis.

•Trabalho de Campo Otimizado: Concentre as inspeções de campo em mudanças confirmadas com localizações precisas. Reduza visitas desnecessárias e aloque recursos de forma eficiente.

•Eficiência Semi-Automatizada: Funciona com satélites ou fotos georreferenciadas do Google. Embora não filtre 100% do ruído, economiza horas na limpeza final, equilibrando automação com validação especializada.

🛠️ Guia de Instalação

Siga estas etapas para instalar e configurar o Urban Change Aid no QGIS.

1.Instale o QGIS: Baixe e instale o QGIS versão 3.40 LTR (Long Term Release) no site oficial.

2.Instale o Orfeo Toolbox (OTB): Baixe o OTB para o seu sistema operacional e extraia-o para um diretório de fácil acesso, por exemplo, C:/otb910.

3.Instale o Plugin: Extraia o arquivo ZIP do plugin para o diretório de plugins do QGIS: C:\Users\seu_nome_de_usuário]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\urban_change_aid

4.Configure o OTB no QGIS: No QGIS, vá em Opções → Processamento → Provedores → OTB e configure:

•Pasta de aplicativos OTB: C:/otb910/lib/otb/applications

•Pasta OTB: C:/otb910

5.Carregue o Plugin: Instale o Plugin Reloader do repositório de plugins do QGIS e use-o para recarregar o Urban Change Aid. Se for bem-sucedido, o plugin aparecerá no menu Plugins.

🚀 Pronto para Transformar Sua Análise Urbana?

Baixe o Urban Change Aid e comece a detectar mudanças urbanas com fluxos de trabalho objetivos e baseados em métricas.

Especificação Técnica
Detalhe
Versão QGIS
3.40 LTR em diante
Licença
GNU GPL v3
Linguagem
Python
Repositório
[[Link para o GitHub]](https://github.com/mikadishen/urban_change_aid/)
[[Link para o Site]](https://urbanchang-gb98hazp.manus.space)

