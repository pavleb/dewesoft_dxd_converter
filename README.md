# Converting Dewesoft DXD files

Dewesoft has one of the best data acquisition systems on the market. 
It is used in many industries and applications. The data is stored in a proprietary format called DXD. 
Dewesoft provides free but not open source libraries to read the data.
They are available for Windows and Linux platforms.
Additionally, there are several python wrappers available to read the data.
It turns out that the format is not that complicated and can be read with a few lines of code.

## Structure of the DXD file
The data are stored in pages.
The format is in little endian.

The first task is to locate the so-called table of contents or using DXD notation the ``INDEX``.
This is available in the first copuple of 100B in the file.
An example of the ``INDEX`` is shown below:
```hexdump
00000000  4d 55 4c 54 49 5f 53 54  52 45 41 4d 5f 46 49 4c  |MULTI_STREAM_FIL|
00000010  45 5f 56 45 52 30 32 31  30 36 00 00 00 44 65 77  |E_VER02106...Dew|
00000020  65 73 6f 66 74 5f 44 61  74 61 5f 37 2e 78 5f 5f  |esoft_Data_7.x__|
00000030  5f 5f 64 79 6e 61 6d 69  63 56 45 52 58 33 20 53  |__dynamicVERX3 S|
00000040  50 34 20 28 52 45 4c 45  41 53 45 2d 31 38 30 39  |P4 (RELEASE-1809|
00000050  32 30 29 00 00 00 00 00  00 00 00 00 00 00 00 00  |20).............|
00000060  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
00000070  00 00 00 00 00 00 00 00  00 00 00 00 00 00 7e 00  |..............~.|
00000080  00 00 00 00 00 00 5f 5f  5f 49 4e 44 45 58 00 02  |......___INDEX..|
00000090  00 00 00 00 00 00 00 02  00 00 00 00 00 00 f8 03  |................|
000000a0  00 00 00 00 00 00 00 e0  07 00 00 00 4e 4c 4b 57  |............NLKW|
000000b0  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
```
In our case the ``__INDEX`` is at the location ``0x80`` and the location is ``0x0200``, which are the bytes just after the tag ``__INDEX`` swapped from little endian.

## Page structure
Each page has a starting tag ``PAG1``.
An example of the first page and location ``0x0200`` obtained using ``hexdump -C`` is shown below:
```hexdump
00000200  50 41 47 31 00 00 00 00  ff ff ff ff ff ff ff ff  |PAG1............|
00000210  ff ff ff ff ff ff ff ff  ff ff ff ff 00 00 00 00  |................|
```

The data can be stored in chunks that can spread multiple pages.
One can analyse the page structure in chunks of 8 bytes.
After the tag ``PAG1`` there are 5 bytes of ``0x00``.
The next 8 bytes is the location of the previous page or ``0xffffffffffffffff`` if it is the first page.
The next 8 bytes is the location of the next page or ``0xffffffffffffffff`` if it is the last page.


## Index page
The index page is the first page in the file in our case located at ``0x0200``.
Full dump is shown below:
```hexdump
00000200  50 41 47 31 00 00 00 00  ff ff ff ff ff ff ff ff  |PAG1............|
00000210  ff ff ff ff ff ff ff ff  ff ff ff ff 00 00 00 00  |................|
00000220  16 00 00 00 04 00 00 00  00 00 00 00 4d 45 41 53  |............MEAS|
00000230  49 4e 46 4f 00 0a 00 00  00 00 00 00 00 0a 00 00  |INFO............|
00000240  00 00 00 00 9a 00 00 00  00 00 00 00 00 e0 01 00  |................|
00000250  00 00 32 00 00 00 00 00  00 00 53 45 54 55 50 00  |..2.......SETUP.|
00000260  00 00 00 0c 00 00 00 00  00 00 00 cc 00 00 00 00  |................|
00000270  00 00 68 0f 00 00 06 00  00 00 00 e0 1f 00 00 00  |..h.............|
00000280  60 00 00 00 00 00 00 00  42 49 4e 46 4f 00 00 00  |`.......BINFO...|
00000290  00 ec 00 00 00 00 00 00  00 ec 00 00 00 00 00 00  |................|
000002a0  40 00 00 00 00 00 00 00  00 e0 03 00 00 00 8e 00  |@...............|
000002b0  00 00 00 00 00 00 42 44  41 54 41 00 00 00 00 f0  |......BDATA.....|
000002c0  00 00 00 00 00 00 00 00  01 00 00 00 00 00 40 00  |..............@.|
000002d0  00 00 04 00 00 00 00 e0  03 00 00 00 bc 00 00 00  |................|
000002e0  00 00 00 00 45 56 45 4e  54 53 00 00 00 08 01 00  |....EVENTS......|
000002f0  00 00 00 00 00 08 01 00  00 00 00 00 96 00 00 00  |................|
00000300  00 00 00 00 00 e0 0f 00  00 01 ea 00 00 00 00 00  |................|
00000310  00 00 52 45 47 49 4e 46  4f 00 00 04 01 00 00 00  |..REGINFO.......|
00000320  00 00 00 04 01 00 00 00  00 00 8f 00 00 00 00 00  |................|
00000330  00 00 00 e0 01 00 00 00  18 01 00 00 00 00 00 00  |................|
00000340  44 42 44 41 54 41 00 00  00 18 01 00 00 00 00 00  |DBDATA..........|
```
One can notice that there are text tags that are followed by the location of the data.
At the present we are interested in ``DBDATA`` and ``SETUP``.
The tag ``DBDATA`` is the location of the binary data.
The tag ``SETUP`` is the location of the XML data describing the DAQ setup with all correction factors and calibration data.

## Setup page
The setup page is the page that contains the XML data.
From the index above the ``SETUP`` is located at ``0x0c00``.
Those are the bytes located after +3B from the end of the tag ``SETUP``.
The ``hexdump`` of the begining of the ``SETUP`` page is shown below:
```hexdump
00000c00  50 41 47 31 00 00 00 00  ff ff ff ff ff ff ff ff  |PAG1............|
00000c10  00 2c 00 00 00 00 00 00  01 00 00 00 00 00 00 00  |.,..............|
00000c20  3c 3f 78 6d 6c 20 76 65  72 73 69 6f 6e 3d 22 31  |<?xml version="1|
00000c30  2e 30 22 20 65 6e 63 6f  64 69 6e 67 3d 22 55 54  |.0" encoding="UT|
00000c40  46 2d 38 22 3f 3e 0d 0a  3c 44 61 74 61 46 69 6c  |F-8"?>..<DataFil|
00000c50  65 53 65 74 75 70 3e 0d  0a 09 3c 53 79 73 74 65  |eSetup>...<Syste|
```
From the page structure we can see that the next page is located at ``0x2c00`` and that the there is no previous page since the address is ``0xffffffffffffffff`` or in decimal -1.
The actual data starts with offset of ``0x20``B from the beginning of the page.
In order to extract the complete XML one should parse all of the remaining pages.

So the header of page at ``0x2c00`` is shown below:
```hexdump
00002c00  50 41 47 31 01 00 00 00  00 0c 00 00 00 00 00 00  |PAG1............|
00002c10  00 4c 00 00 00 00 00 00  01 00 00 00 00 00 00 00  |.L..............|
00002c20  6e 67 6c 65 53 65 6e 73  6f 72 3e 54 72 75 65 3c  |ngleSensor>True<|
```
It is clear that the previous page is at ``0x0c00`` and the next page is at ``0x4c00``.
Following all the way to the last page its header is shown below:
```hexdump
0000cc00  50 41 47 31 06 00 00 00  00 ac 00 00 00 00 00 00  |PAG1............|
0000cc10  ff ff ff ff ff ff ff ff  01 00 00 00 00 00 00 00  |................|
0000cc20  61 70 74 69 6f 6e 3e 0d  0a 09 09 09 09 09 09 09  |aption>.........|
```
From the page structure we can see that the previous page is located at ``0xac00`` and that the there is no next page since the address is ``0xffffffffffffffff`` or in decimal -1.
So starting with offset of ``0x20``B from the beginning of the page one can extract the XML data.
Concatenating all this together will give the complete XML data that can be easily parsed.

## Structure of the binary data
From the index page tag ``DBDATA`` we can see that the binary data is located at ``0x011800``.
The header of the page is shown below:
```hexdump
00011800  50 41 47 31 00 00 00 00  fe ff ff ff ff ff ff ff  |PAG1............|
00011810  fe ff ff ff ff ff ff ff  06 00 00 00 e0 5f 21 00  |............._!.|
00011820  a8 67 e8 67 04 68 5f 68  73 67 47 68 0b 68 5b 68  |.g.g.h_hsgGh.h[h|
```
Unlike the previous pages, the values for the next and previous page are not ``0xffffffffffffffff`` but ``0xfeffffffffffffff`` or -2 in decimal.
From the patterns in the files we deduce that after the next page segment there are 4B of what we call page type, in this case ``0x06``.
The last 4B are the size of the data in the page, in this case ``0x215fe0`` or 2160000B.
This means that the next page will start at ``0x011800 + 0x215fe0 + 0x20 = 0x227800``.
The data starts at offset of ``0x20``B from the beginning of the page.
The dump at ``0x227800`` is shown below:
```hexdump
00227800  50 41 47 31 00 00 00 00  fe ff ff ff ff ff ff ff  |PAG1............|
00227810  fe ff ff ff ff ff ff ff  08 00 00 00 e0 db 00 00  |................|
00227820  00 5e cd 46 00 76 d4 46  be 82 d0 46 4c 61 df 3e  |.^.F.v.F...FLa.>|
```
The same pattern is repeated.
For this page the page type is ``0x08`` and the size of the data is ``0xdbe000``.
Following the same pattern one can parse the complete file and locate the begining of each page its type and data length.
In such a way one can extract the table of contents of the file.

## Reading the binary data
In our case the DAC was 16bit.
This is also visible from the setup XML.
The data is stored in little endian in ``uint16_t`` format.
**I assume that if you have 24bit DAC the data will be stored with ``uint32_t``.**
In our cases we have observed 3 types of pages:
- ``0x06``: This is the page that contains the data.
- ``0x08`` and
- ``0x0a``.

I have not observed any other types of pages and sadly I do not have information regarding types ``0x08`` and ``0x0a``.

For multichannel data the data is stored in interleaved format with chunks of 1000 samples.
The page sizes are not always multiple of 1000 samples.
Therefore the remaining samples should be concatenated with the next page.

## Converting the data from ``uint`` to ``float``
From one binary page one can read the data with the following python code:
```python
# data_len is the size of the data in bytes
# data_start is the location of the data start in the file
# A is the array containing the data
dt = np.dtype(np.int16)
dt = dt.newbyteorder('<')    
B = np.frombuffer(A[data_start:data_start+data_len],dtype=dt)
```

Assuming that all data is read and properly concatenated one can convert the data to ``float`` with the following code:
```python
# number_of_channels is the number of channels
# wished_channel is the channel that you want to extract
assert wished_channel < number_of_channels
reshaped_array = B.reshape(-1, 1000)
eI = reshaped_array[wished_channel::number_of_channels,:].reshape(1,-1).squeeze()
```
The conversion from float can be made using the data from the XML setup.
Assuimg that the data is stored in the variable ``eI`` and the XML data is stored in the variable ``xml_data`` one can convert the data with the following code:
```python
import xml.etree.ElementTree as ET
root = ET.fromstring(tostr(np.concatenate(xml_data)).strip())
setup = list(root.iter('DewesoftSetup'))[0]
slots = setup.findall('.//Slot') # number of channels

scale = setup.findall(f".//Slot[@Index='{wished_channel}']/AmplScale")[0]
scale = float(scale.text)
interscept = setup.findall(f".//Slot[@Index='{wished_channel}']/AmplOffset")[0]
interscept = float(interscept.text)

scale = scale*10/(np.iinfo(np.uint16).max+1)

converted = eI*scale - interscept
```
