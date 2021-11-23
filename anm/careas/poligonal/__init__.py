from .util import (
    formatMemorial,
    readMemorial,
    forceverdPoligonal       
)

def test(verbose=True, coverage=False):
    """
    Run the test suite.
    Uses `py.test <http://pytest.org/>`__ to discover and run the tests.
    Parameters
    ----------
    verbose : bool
        If ``True``, will print extra information during the test run.
    coverage : bool
        If ``True``, will run test coverage analysis on the code as well.
        Requires ``pytest-cov``.
    Raises
    ------
    AssertionError
        If pytest returns a non-zero error code indicating that some tests have
        failed.
    """
    import pytest

    package = __name__
    args = []
    if verbose:
        args.append("-vv")
    if coverage:
        args.append("--cov={}".format(package))
        args.append("--cov-report=term-missing")
    args.append("--pyargs")
    args.append(package)    
    status = pytest.main(args)
    assert status == 0, "Some tests have failed."