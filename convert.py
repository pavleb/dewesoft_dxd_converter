"""
Utility for reading DXD files
"""
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from tqdm import tqdm


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

    def get_addr(self, A,key, offset = 2):
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
        return self.get_addr(A,'SETUP',3)
    
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
        self.devices = self.setup.findall(".//Device[@Type='AI']")[0]
        slots = self.devices.findall('.//Slot')

        stored_channels = self.setup.findall(".//StoredChannels/Channel")
        self.number_of_channels = sum(['AI' in x.attrib['Index'] for x in stored_channels])

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
    

