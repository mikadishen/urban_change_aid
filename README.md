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

