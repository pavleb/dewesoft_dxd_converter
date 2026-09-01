# tests/test_converter.py
from pathlib import Path
import numpy as np
import dewesoft_dxd_converter as dw
from conftest import get_fixture_files
import pytest

# Find all .dxz files dynamically at test setup time
DXZ_FILES = get_fixture_files(".dxz")

@pytest.mark.parametrize("file_path", DXZ_FILES, ids=lambda p: p.name)
def test_all_dxz_files_convert(file_path: Path):
    # dxz_file is passed in automatically as a pathlib.Path object
    reader = dw.DXZReader(file_path)
    
    # 1. Assert basic structure returned
    assert reader is not None
    # assert isinstance(reader.data, dict)  # or whatever your converter outputs

def test_channel_setup():
    reader = dw.DXZReader(r'tests/fixtures/316_sin_exp[f1000][n40]-ext-[A2.5]_2026_04_02_221349.dxz')
    assert reader.measurement_setup.sample_rate == 100000.0
    assert reader.measurement_setup.num_channels == 8
    assert reader.measurement_setup.blockSize == 1000

    assert reader.measurement_setup.num_channels == len(reader.measurement_setup.channels)

    for i, chan in enumerate(reader.measurement_setup.channels):
        if i == 7:
            name = 'I'
        else:
            name = f'U{i+1}'
        assert isinstance(chan, dw.ChannelConfig)
        assert chan.name == name


def test_channel_data():
    reader = dw.DXZReader(r'tests/fixtures/316_sin_exp[f1000][n40]-ext-[A2.5]_2026_04_02_221349.dxz')
    ch1_data = reader.get_samples(7)
    assert isinstance(ch1_data, np.ndarray)
    assert ch1_data.shape[0]/100000.0 == 2.32
    assert ch1_data.shape == (232000,)