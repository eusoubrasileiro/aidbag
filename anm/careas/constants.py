from pathlib import Path
import os, re

userhome = str(Path.home()) # get userhome folder
# eventos que inativam or ativam processo
__secor_path__ = os.path.join(userhome, r'Documents\Controle_Areas')
__eventos_scm__ = os.path.join(__secor_path__,
                        r'Secorpy\eventos_scm_12032020.xls')
__secor_timeout__ = 4*60 # sometimes sigareas server/r. interferncia takes a long long time to answer 

scm_timeout=(2*60)

# Processes Regex
# groups 
regex_processg = re.compile('(\d{0,3})\D*(\d{1,3})\D([1-2]\d{3})') # use regex_processg return tupple groups
# without groups
regex_process = re.compile('\d{0,3}\D*\d{1,3}\D[1-2]\d{3}') # use regex_process.search(...) if None didn't find 
# explanation: [1-2]\d{3} years from 1900-2999

def test_regex_process():
    testtext = "847/1945,xx2.537/2016,832537-2016,48403.832.537/2016-09,832.537/2016-09"
    result = re.findall(regex_processg, testtext)
    expected = [('84', '7', '1945'),
    ('2', '537', '2016'),
    ('832', '537', '2016'),
    ('832', '537', '2016'),
    ('832', '537', '2016')]
    assert  result == expected

# test regex when imported 
test_regex_process()


# SCM URL LIST
# TODO complete the list as contants 
#'https://sistemas.anm.gov.br/SCM/Intra/site/admin/dadosProcesso.aspx' # might change again
scm_dados_processo_main_url='https://sistemas.anm.gov.br/scm/intra/site/admin/dadosprocesso.aspx'

# HTML tags for SCM main page
# static field
scm_data_tags = { # "data name" ; soup.find fields( "tag", "attributes")
    'prioridade'            : ['span',  { 'id' : "ctl00_conteudo_lblDataPrioridade"} ], # pode estar errada
    'area'                  : ['span',  { 'id' : 'ctl00_conteudo_lblArea'} ],
    'UF'                    : ['span',  { 'id' : 'ctl00_conteudo_lblUF'} ],
    'NUP'                   : ['span',  { 'id' : 'ctl00_conteudo_lblNup'} ],
    'tipo'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoRequerimento'} ],
    'fase'                  : ['span',  { 'id' : 'ctl00_conteudo_lblTipoFase'} ],
    'data_protocolo'        : ['span',  { 'id' : 'ctl00_conteudo_lblDataProtocolo'} ], # pode estar vazia
    'associados'            : ['table', { 'id' : 'ctl00_conteudo_gridProcessosAssociados'} ],
    'substancias'           : ['table', { 'id' : 'ctl00_conteudo_gridSubstancias'} ],
    'eventos'               : ['table', { 'id' : 'ctl00_conteudo_gridEventos'} ],
    'municipios'            : ['table', { 'id' : 'ctl00_conteudo_gridMunicipios'} ],
    'ativo'                 : ['span',  { 'id' : 'ctl00_conteudo_lblAtivo'} ]
}

# workflows 

# Deve ser atualizado o código se o modelo favarito for modificado
# 0 -  1537881	Retificação Resumida Alvará e Aprovo do RFP
# 1 - 1947449	Parecer Técnico - Correção áreas e deslocamentos
# 2 - 1618347	Formulário 1 - Lavra - Pré-Prenchido
# 3 - 2725631	Chefe SECOR Requerimento: Recomendo Analise de Plano
# 4 - 1133380	Chefe SECOR Requerimento: Recomenda publicar exigência opção
# 5 - 2725639	Chefe SECOR Requerimento: Recomenda publicar indeferimento por Interferência Total
# 6 - 1206693	Chefe SECOR Requerimento: Recomendo Analise de Cessão Parcial
# 7 - 1243175	Chefe SECOR Requerimento: Recomendo Analise de Plano (híbrido)
# 8 - 1453503	Chefe SECOR Requerimento de Lavra: Recomendo aguardar cumprimento de exigências
# 9 - 1995116	Chefe SECOR Requerimento de Lavra: com Retificação de Alvará
# 10 - 1995741	Chefe SECOR Requerimento de Lavra: Recomendo encaminhar para preenchimento de check-list
# 11 - 2052065	Chefe SECOR Requerimento de Lavra: Encaminhar avaliar necessidade de reavaliar reservas - redução de área
# 12 - 3044089  Chefe SECOR Requerimento: Recomendo Só Análise de Plano 100%

mcodigos = ['1537881', '1947449', '1618347', '2725631', '1133380', '2725639', 
'1206693', '1243175', '1453503', '1995116', '1995741', '2052065', '3044089']

docs_externos_sei_tipo = [ 'Estudo',
        'Minuta', 'Minuta', 'Estudo', 'Minuta', 'Minuta', u'Formulário']

# needs u"" unicode string because of latim characters
docs_externos_sei_txt = [ u"de Retirada de Interferência", # Nome na Arvore
        u"Pré de Alvará", 'de Licenciamento', u"de Opção", 'de Portaria de Lavra',
        u"de Permissão de Lavra Garimpeira", u"1 Análise de Requerimento de Lavra SECOR-MG"]
