"""
Utility for reading DXD files
"""
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from tqdm import tqdm
import zipfile
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DewesoftEventRecord:
    event_id: int
    event_type: int  # 1 for etStart, 2 for etStop
    bucket_index: int
    sample_offset: int
    
    @property
    def true_sample_index(self, block_size: int = 1000) -> int:
        return (self.bucket_index * block_size) + self.sample_offset

class DewesoftEventsParser:
    def __init__(self, file_path: str):
        self.raw_data = np.fromfile(file_path, dtype=np.uint8)
        self.signature = np.array([69, 118, 101, 110, 116, 83], dtype=np.uint8) # "EventS"
        
    def parse(self) -> List[DewesoftEventRecord]:
        records = []
        found_count = 0
        
        # Scan for the 0x86 "Envelope"
        for i in range(len(self.raw_data) - 30):
            if self.raw_data[i] == 0x86 and np.array_equal(self.raw_data[i+1:i+7], self.signature):
                
                # THE FIX: The Event Type is the 4-byte integer immediately PRECEDING the 0x86
                # We look at i-4 to i
                if i >= 4:
                    e_type = self.raw_data[i-4:i].view(np.int32)[0]
                else:
                    e_type = 0 # Fallback for safety
                
                record = self._parse_envelope(i, found_count, e_type)
                if record:
                    records.append(record)
                    found_count += 1
        
        return records

    def _parse_envelope(self, start_idx: int, e_id: int, e_type: int) -> Optional[DewesoftEventRecord]:
        # Search window within the 0x86 frame
        search_limit = min(start_idx + 100, len(self.raw_data))
        body_start = start_idx + 7 
        
        for j in range(body_start, search_limit - 12):
            prop_id = self.raw_data[j:j+4].view(np.int32)[0]
            
            if prop_id == 6:
                # Based on your correct mapping:
                # [j+4:j+8]  -> Bucket Index
                # [j+8:j+12] -> Sample Offset
                bucket_idx = self.raw_data[j+4:j+8].view(np.int32)[0]
                offset = self.raw_data[j+8:j+12].view(np.int32)[0]
                
                return DewesoftEventRecord(
                    event_id=e_id,
                    event_type=e_type,
                    bucket_index=bucket_idx,
                    sample_offset=offset
                )
        return None

@dataclass
class ChannelConfig:
    name: str
    bits: int
    scale: float
    offset: float
    range_min: float
    range_max: float

    @property
    def computed_scale(self) -> float:
        """
        The 'Golden Multiplier' used to convert raw binary to engineering units.
        Logic: (AmplScale * 10) / 2^Bits
        """
        return (self.scale * 10.0) / (2**self.bits)

    def scale_data(self, raw_data: np.ndarray) -> np.ndarray:
        """
        Applies scaling and offset to a numpy array of raw integers.
        """
        # raw_data is likely np.int16 or np.int32 based on BitsLog
        return (raw_data.astype(np.float64) * self.computed_scale) - self.offset

@dataclass
class MeasurementSetup:
    sample_rate: float
    blockSize: int
    channels: List[ChannelConfig] = field(default_factory=list)
    
    @property
    def num_channels(self) -> int:
        return len(self.channels)

    def get_channel_by_name(self, name: str) -> ChannelConfig:
        for ch in self.channels:
            if ch.name == name:
                return ch
        raise ValueError(f"Channel {name} not found.")


class DXZReader:
    def __init__(self, filename):
        """
        DXZ files are ZIP of multiple files each corresponding to a particular page.
        The converter can accept a filename, whose content is extracted in a temporary folder or a folder that contais already expanded files

        filename - the DXZ file that has to be processed
        """
        if not Path(filename).exists():
            raise Exception('File does not exist')
        
        if Path(filename).is_dir():
            self.__process_folder(filename)
        else:
            self.__process_file(filename)        

        
    
    def __process_folder(self, folder):
        folder_path = Path(folder)
        
        events_file = folder_path / 'EVENTS'
        if events_file.exists():
            parser = DewesoftEventsParser(str(events_file))
            self.events = parser.parse()
        else:
            self.events = []
            
        setup_file = folder_path / 'SETUP'
        if setup_file.exists():
            self.measurement_setup = self._process_setup(str(folder_path))
        else:
            self.measurement_setup = None

        dbdata_file = folder_path / 'DBDATA'
        if dbdata_file.exists() and self.measurement_setup is not None:
            A = np.fromfile(str(dbdata_file), dtype=np.uint8)
            dt = np.dtype(np.int16)
            dt = dt.newbyteorder('<')    
            B = np.frombuffer(A, dtype=dt)
            self.dbdata_c = np.reshape(B, (-1, self.measurement_setup.blockSize))
        else:
            self.dbdata_c = None
            
    def get_samples(self, wish: int):
        if self.dbdata_c is None or self.measurement_setup is None:
            raise Exception("Data not loaded properly or missing setups.")
            
        number_of_channels = self.measurement_setup.num_channels
        scale = self.measurement_setup.channels[wish].scale
        nsl = scale * 1 / (np.iinfo(np.uint16).max + 1) 
        
        ch_data = self.dbdata_c[wish::number_of_channels, :].reshape(1, -1).squeeze()
        
        limit = None
        if self.events and len(self.events) > 1:
            limit = self.events[1].sample_offset
    
            
        if (limit is not None) and limit != 0:
            return self.measurement_setup.channels[wish].scale_data(ch_data[:limit])
        else:
            return self.measurement_setup.channels[wish].scale_data(ch_data)

    
    def __process_file(self, filename):
        # Unzip file into temp folder
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(filename) as zip_ref:
                zip_ref.extractall(temp_dir)
            self.__process_folder(temp_dir)

    def __sample_date_read(self, folder_path: str) -> float:
        with open(Path(folder_path) / 'INFO_', 'r') as f:
            xml_data = f.read()
        
        root = ET.fromstring(xml_data)

        # Global Sample Rate (assuming the first one is the master)
        sr_element = root.find('.//SampleRate')
        sample_rate = float(sr_element.text) if sr_element is not None else 0.0
        return sample_rate

    def _process_setup(self, folder_path: str) -> MeasurementSetup:
        with open(Path(folder_path) / 'SETUP', 'r') as f:
            xml_data = f.read()
        
        root = ET.fromstring(xml_data)

        # Global Sample Rate (assuming the first one is the master)
        sr_element = root.find('.//SampleRate')
        sr_blockSize = root.find('.//BlockSize')
        sample_rate = self.__sample_date_read(folder_path)
        
        if sr_blockSize is not None:
            blockSize = int(sr_blockSize.text)
        else:
            raise Exception('BlockSize')
        
        setup = MeasurementSetup(sample_rate=sample_rate, blockSize=blockSize)

        # Devices and Slots
        for device in root.findall('.//Device[@Type="AI"]'):
            for slot in device.findall('.//Slot'):
                used = slot.find('.//Used')
                if used is None:
                    continue
                if used.text == 'True':
                    # Construct the ChannelConfig
                    ch = ChannelConfig(
                        name=slot.find('.//Name').text,
                        bits=int(slot.find('.//BitsLog').text),
                        scale=float(slot.findall('.//AmplScale')[0].text),
                        offset=float(slot.findall('.//AmplOffset')[0].text),
                        range_min=float(slot.find('.//RangeMin').text),
                        range_max=float(slot.find('.//RangeMax').text)
                    )
                    setup.channels.append(ch)
                    
        return setup

class DXDReader:
    def __init__(self, filename):
        self.filename = filename
        self.data = None
        self.__file = None

        self.parse_setup()
        self.parse_pages()
    
    def open(self):
        if self.__file is not None:
            self.__file.close()
        self.__file = open(self.filename, 'rb')

    def close(self):
        if self.__file is not None:
            self.__file.close()
            self.__file = None

    def read_chunk(self, start, size):
        if self.__file is None:
            self.open()
        
        self.__file.seek(start)
        return np.frombuffer(self.__file.read(size), dtype='uint8')

    def tostr(self, A):
        """
        Converting a list of integers into characters
        """
        # return A.tobytes().decode('utf-8')
        return ''.join([chr(x) for x in A])

    def get_address(self, A,key):
        s = self.tostr(A)
        return s.find(key)

    def get_addr(self, A,key):
        offset = 8 - len(key)
        if offset < 0:
            raise Exception('Key too long')
        ind = self.search_key(A,key)
        if ind < 0:
            raise Execption('Not found')
            
        st = len(key) + ind + offset
        dt = np.dtype(np.uint32)
        dt = dt.newbyteorder('<')
        return np.frombuffer(A[st:st+8],dtype=dt)[0]

    def search_key(self, A, key):
        s = self.tostr(A)
        return s.find(key)

    def get_index(self):
        A = self.read_chunk(0x00,0x200)
        return self.get_addr(A,'__INDEX')
    
    def get_dbdata(self):
        A = self.read_chunk(self.get_index(),2048)
        return self.get_addr(A,'DBDATA')
    
    def get_xml_location(self):
        A = self.read_chunk(self.get_index(),2048)
        return self.get_addr(A,'SETUP')
    
    def get_page_len(self, A):
        page_start = 0
        ind = page_start + 8
        while A[ind] >= 0xfe:
            ind += 1
        dt = np.dtype(np.uint32)
        dt = dt.newbyteorder('<')

        dtpn = np.dtype(np.int32)
        dtpn = dtpn.newbyteorder('<')

        prev_page = np.frombuffer(A[page_start+8:page_start+16], dtype=dtpn)[0]
        next_page = np.frombuffer(A[page_start+8+8:page_start+16+8], dtype=dtpn)[0]

        
        start = ind+4


        pg_type = np.frombuffer(A[ind:start], dtype=dt)[0]
        return np.frombuffer(A[start:start+4],dtype=dt)[0], start+4, A[page_start + 4], pg_type, prev_page, next_page
        

    def parse_setup(self):
        xml_data = []
        pattern = [0xd, 0xa,0x00,0x00,0x00]
        xml_loc = self.get_xml_location()
        
        while True:
            # print(hex(xml_loc))
            A = self.read_chunk(xml_loc,20480)
            data_len, data_start, page_ser, pg_type, prev_page, next_page = self.get_page_len(A)
            data_start = xml_loc + 0x20
            if next_page > -1:
                xml_data.append(self.read_chunk(data_start, next_page-data_start))#A[data_start:next_page])
                xml_loc = next_page
            else:
                A = A[0x20:]
                n, m = 20480, len(pattern)
                indices = []
                for i in range(n - m + 1):
                    if np.all(A[i:i+m] == pattern):
                        end_ind = i
                        break
                else:
                    # print('Not found')
                    # return A
                    raise Exception()
                xml_data.append(A[:end_ind])
                break

        # return self.tostr(np.concatenate(xml_data)).strip()
        self.root = ET.fromstring(self.tostr(np.concatenate(xml_data)).strip())
        self.setup = list(self.root.iter('DewesoftSetup'))[0]
        self.devices = self.setup.findall(".//Device[@Type='AI']")
        # slots = self.devices.findall('.//Slot')

        stored_channels = self.setup.findall(".//StoredChannels/Channel")
        self.number_of_channels = sum(['AI' in x.attrib['Index'] for x in stored_channels])
        self.sample_rates = [float(sr.text) for sr in self.root.findall('.//SampleRate')]

    @property
    def number_of_devices(self):
        return len(self.devices)

    def parse_pages(self):
        next_db_loc = self.get_dbdata()
        pages = []
        while next_db_loc < Path(self.filename).stat().st_size:
            A = self.read_chunk(next_db_loc,2048)
            data_len, data_start, page_ser, pg_type, prev_page, next_page = self.get_page_len(A)
            pages.append((data_len, next_db_loc + data_start, page_ser, pg_type, prev_page, next_page))
            next_db_loc = next_db_loc + data_start + data_len
            

        self.sep_pages = {}
        for page in pages:
            if page[3] not in self.sep_pages:
                self.sep_pages[page[3]] = []
            self.sep_pages[page[3]].append(page)

    def load_page(self, data_len, data_start, page_ser, page_type, *args):
        dt = np.dtype(np.int16)
        dt = dt.newbyteorder('<')    
        if self.__file is None:
            self.open()

        self.__file.seek(data_start)
        return np.frombuffer(self.__file.read(data_len), dtype=dt)


    def get_channel_info(self):
        channel_info = []
        for device in self.devices:
            slots = device.findall('.//Slot')
            for slot in slots:
                used = slot.find('.//Used')
                if used is None:
                    continue
                if used.text == 'True':
                    name = slot.findall('.//Name')[0].text
                    bits = slot.findall('.//BitsLog')[0].text
                    scale = slot.findall('.//AmplScale')[0].text
                    offset = slot.findall('.//AmplOffset')[0].text
                    rangeMin = slot.findall('.//RangeMin')[0].text
                    rangeMax = slot.findall('.//RangeMax')[0].text
                    channel_info.append({'name': name, 'bits': bits, 'scale': scale, 'offset': offset, 'rangeMin': rangeMin, 'rangeMax': rangeMax})
        return channel_info 

    def get_chanel_name(self, channel):
        assert channel < self.number_of_channels

        name = self.setup.findall(f".//Slot[@Index='{channel}']/OutputChannel/Name")[0].text
        # name = slot.findall('Name')[0].text
        # unit = slot.findall('Unit')[0].text
        # scale = slot.findall('AmplScale')[0].text
        # offset = slot.findall('AmplOffset')[0].text
        return name#, unit, scale, offset

    def get_channel_data(self, wish):
        assert wish < self.number_of_channels

        ext_data = []
        tp = 6
        carry_segment = np.array([])
        for page in tqdm(self.sep_pages[tp]):

            B = self.load_page(*page)
            temp_arr = np.concatenate([carry_segment,B])
            fix_len = len(temp_arr)//(self.number_of_channels * 1000)
            reshaped_array = temp_arr[:fix_len*(self.number_of_channels*1000)].reshape(-1, 1000)

            carry_segment = temp_arr[-(len(temp_arr) % (self.number_of_channels * 1000)):]
            ext_data.append(reshaped_array[wish::self.number_of_channels,:].reshape(1,-1).squeeze())

        scale = self.setup.findall(f".//Slot[@Index='{wish}']/AmplScale")[0]
        scale = float(scale.text)

        interscept = self.setup.findall(f".//Slot[@Index='{wish}']/AmplOffset")[0]
        interscept = float(interscept.text)

        nsl = scale*10/(np.iinfo(np.uint16).max+1) 
        return np.concatenate(ext_data)*nsl - interscept
    

