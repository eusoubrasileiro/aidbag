from . import poligonal
from . import estudos 

from .constants import (
    __secor_path__,
    __eventos_scm__,
    __secor_timeout__,
    regex_processg, 
    regex_process, 
    scm_timeout, 
)

from .SEI import SEI
from .util import ContaPrazo

from .workflows import (
    IncluiDocumentosSEIFolder, 
    EscreveDespacho,
    EstudoBatchRun,
    IncluiDocumentosSEIFoldersFirstN
)