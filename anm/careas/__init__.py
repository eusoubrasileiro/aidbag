from .scm import (
    Processo, 
    ProcessStorage, 
    findfmtPnames,
    findPnames,
    fmtPname,
    numberyearPname,    
)

from .constants import (
    __secor_path__,
    __eventos_scm__,
    __secor_timeout__,
    regex_processg, 
    regex_process, 
    scm_timeout, 
)

from .util import ContaPrazo

from .workflows import (
    IncluiDocumentosSEIFolder, 
    EscreveDespacho,
    EstudoBatchRun,
    IncluiDocumentosSEIFoldersFirstN,
    folder_process
)

# needed for connection so better be here
# widely visible from careas
from ...web import (
    wPageNtlm,
    wPage
)