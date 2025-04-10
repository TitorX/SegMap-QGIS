import os
import sys; sys.path.insert(0, os.path.dirname(__file__))


def classFactory(iface):  # pylint: disable=invalid-name
    """Load SegMap class from file SegMap.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .SegMap import SegMap
    return SegMap(iface)
