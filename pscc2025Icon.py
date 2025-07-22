import os
import struct
import sys

# Constants
NAME_SIZE = 48
DATA_SIZE = 320

class PicInfo:
    """Represents picture information (offset and size)."""
    def __init__(self, offset=0, size=0):
        self.offset = offset
        self.size = size

class IconData:
    """Represents icon data for a single resolution (width, height, x, y, and a list of PicInfo)."""
    def __init__(self, width=0, height=0, x=0, y=0):
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.pics = [PicInfo() for _ in range(8)]

class ResourceIcon:
    """Represents a single resource icon, including its key and data for all resolutions."""
    def __init__(self, buffer_data=None):
        self.key = ""
        # Use a dictionary to hold the four resolution data sets
        self.resolutions = {
            'low': IconData(),
            'high': IconData(),
            'xlow': IconData(),
            'xhigh': IconData()
        }

        if buffer_data:
            # Read Key
            self.key = buffer_data[:NAME_SIZE].decode('ascii').strip('\x00')

            # Read the full 320-byte data block
            data_bytes = buffer_data[NAME_SIZE : NAME_SIZE + DATA_SIZE]
            data = struct.unpack('<' + 'i' * (DATA_SIZE // 4), data_bytes)

            res_keys = ['low', 'high', 'xlow', 'xhigh']
            
            # Unpack dimensions for all 4 resolutions
            for i, key in enumerate(res_keys):
                self.resolutions[key].width = data[i]
                self.resolutions[key].height = data[4 + i]
                self.resolutions[key].x = data[8 + i]
                self.resolutions[key].y = data[12 + i]

            # Unpack offsets and sizes for all 4 resolutions
            for i in range(8):
                self.resolutions['low'].pics[i].offset = data[16 + i]
                self.resolutions['high'].pics[i].offset = data[24 + i]
                self.resolutions['xlow'].pics[i].offset = data[32 + i]
                self.resolutions['xhigh'].pics[i].offset = data[40 + i]
                
                self.resolutions['low'].pics[i].size = data[48 + i]
                self.resolutions['high'].pics[i].size = data[56 + i]
                self.resolutions['xlow'].pics[i].size = data[64 + i]
                self.resolutions['xhigh'].pics[i].size = data[72 + i]

    def to_byte_array(self):
        """Converts the ResourceIcon object back into a byte array for saving."""
        buffer_list = []

        # Key
        key_bytes = self.key.encode('ascii')
        buffer_list.extend(key_bytes)
        buffer_list.extend([0] * (NAME_SIZE - len(key_bytes)))

        # Data
        res_keys = ['low', 'high', 'xlow', 'xhigh']
        
        # Pack dimensions (Width, Height, X, Y)
        for field in ['width', 'height', 'x', 'y']:
            for key in res_keys:
                value = getattr(self.resolutions[key], field)
                buffer_list.extend(struct.pack('<i', value))
        
        # Pack Offsets
        for key in res_keys:
            for i in range(8):
                buffer_list.extend(struct.pack('<i', self.resolutions[key].pics[i].offset))
        
        # Pack Sizes
        for key in res_keys:
            for i in range(8):
                buffer_list.extend(struct.pack('<i', self.resolutions[key].pics[i].size))

        return bytes(buffer_list)


class IconResources:
    """Manages a collection of ResourceIcon objects and handles file operations."""
    def __init__(self, index_file_name):
        self.index_file_name = os.path.basename(index_file_name)
        self.directory_path = os.path.dirname(index_file_name)
        
        self.name = ""
        self.low_resolution_data_file = ""
        self.high_resolution_data_file = ""
        self.xlow_resolution_data_file = ""
        self.xhigh_resolution_data_file = ""
        
        self.icons = []
        
        self._marker_index = [0] * 5

        try:
            with open(index_file_name, 'rb') as f:
                buf = f.read()
        except FileNotFoundError:
            print(f"Error: Index file not found at {index_file_name}")
            sys.exit(1)

        # Read header section
        # Using splitlines is safer for text-based headers in binary files
        header_part = buf[:512] # Read first 512 bytes for safety
        lines = header_part.split(b'\n')
        
        self.name = lines[0].decode('ascii').rstrip('\x00').strip()
        self.low_resolution_data_file = lines[1].decode('ascii').rstrip('\x00').strip()
        self.high_resolution_data_file = lines[2].decode('ascii').rstrip('\x00').strip()
        self.xlow_resolution_data_file = lines[3].decode('ascii').rstrip('\x00').strip()
        self.xhigh_resolution_data_file = lines[4].decode('ascii').rstrip('\x00').strip()

        # Calculate header size dynamically
        header_size = len(self.name.encode('ascii')) + len(self.low_resolution_data_file.encode('ascii')) + \
                      len(self.high_resolution_data_file.encode('ascii')) + len(self.xlow_resolution_data_file.encode('ascii')) + \
                      len(self.xhigh_resolution_data_file.encode('ascii')) + 5 # 5 for newline chars
        
        # Find the actual start of the binary data block by searching for the first icon key
        # This is more robust than relying on fixed marker indexes.
        first_key_name = b"Spinner_12" # First known key
        offset = buf.find(first_key_name)
        
        # Fallback if the key isn't found (should not happen in a valid file)
        if offset == -1:
            print("Error: Could not determine the start of the icon data block.")
            sys.exit(1)

        struct_size = NAME_SIZE + DATA_SIZE
        
        count = (len(buf) - offset) // struct_size
        
        for i in range(count):
            start_index = offset + i * struct_size
            end_index = start_index + struct_size
            dst = buf[start_index:end_index]
            self.icons.append(ResourceIcon(dst))

    def _output_index_file(self, working_directory):
        """Generates and writes the index file."""
        # Reconstruct the exact original header to avoid any padding/spacing issues
        with open(os.path.join(self.directory_path, self.index_file_name), 'rb') as f_orig:
            original_buf = f_orig.read()

        first_key_name = b"Spinner_12"
        offset = original_buf.find(first_key_name)
        header_bytes = original_buf[:offset]
        
        # Start the new file with the original header
        buf = bytearray(header_bytes)

        # Append the icon data
        for icon in self.icons:
            buf.extend(icon.to_byte_array())

        output_path = os.path.join(working_directory, self.index_file_name)
        with open(output_path, 'wb') as f:
            f.write(buf)

    def pack(self, working_directory):
        """Packs icon images into data files and updates the index file."""
        low_buf = bytearray(b'fdrq')
        high_buf = bytearray(b'fdrq')

        # We assume XLow and XHigh .dat files are not being modified
        xlow_path = os.path.join(self.directory_path, self.xlow_resolution_data_file)
        xhigh_path = os.path.join(self.directory_path, self.xhigh_resolution_data_file)
        if os.path.exists(xlow_path):
             with open(xlow_path, 'rb') as f:
                 xlow_buf = bytearray(f.read())
        if os.path.exists(xhigh_path):
             with open(xhigh_path, 'rb') as f:
                 xhigh_buf = bytearray(f.read())

        low_offset = len(low_buf)
        high_offset = len(high_buf)

        for icon in self.icons:
            # This loop now handles ALL icons, including the splash screen, using their correct names.
            # The special "if 'Splash' in icon.key" block has been removed.
            
            # --- Repack Low Resolution ---
            for i in range(8):
                # Check if a file exists to be packed. We use the original size as a hint
                # that a resource is supposed to be here.
                if icon.resolutions['low'].pics[i].size > 0:
                    icon_file = os.path.join(working_directory, "Low", f"{icon.key}_s{i}.png")
                    if os.path.exists(icon_file):
                        with open(icon_file, 'rb') as f:
                            data = f.read()
                        # Update the icon's offset and size to the new location in the packed file
                        icon.resolutions['low'].pics[i].offset = low_offset
                        icon.resolutions['low'].pics[i].size = len(data)
                        low_buf.extend(data)
                        low_offset += len(data)

            # --- Repack High Resolution ---
            for i in range(8):
                if icon.resolutions['high'].pics[i].size > 0:
                     icon_file = os.path.join(working_directory, "High", f"{icon.key}_s{i}.png")
                     if os.path.exists(icon_file):
                         with open(icon_file, 'rb') as f:
                             data = f.read()
                         # Update the icon's offset and size to the new location in the packed file
                         icon.resolutions['high'].pics[i].offset = high_offset
                         icon.resolutions['high'].pics[i].size = len(data)
                         high_buf.extend(data)
                         high_offset += len(data)

        # Write out the new DAT files and the corrected index
        with open(os.path.join(working_directory, self.low_resolution_data_file), 'wb') as f:
            f.write(low_buf)
        with open(os.path.join(working_directory, self.high_resolution_data_file), 'wb') as f:
            f.write(high_buf)
        
        self._output_index_file(working_directory)

    def extract(self, working_directory):
        """Extracts icon images from data files based on the index."""
        os.makedirs(working_directory, exist_ok=True)
        # Create all four directories
        for res_folder in ["Low", "High", "XLow", "XHigh"]:
             os.makedirs(os.path.join(working_directory, res_folder), exist_ok=True)

        # A map to link resolution keys to filenames
        data_files = {
            'low': self.low_resolution_data_file,
            'high': self.high_resolution_data_file,
            'xlow': self.xlow_resolution_data_file,
            'xhigh': self.xhigh_resolution_data_file,
        }
        
        buffers = {}
        for key, filename in data_files.items():
            file_path = os.path.join(self.directory_path, filename)
            try:
                with open(file_path, 'rb') as f:
                    buffers[key] = f.read()
            except FileNotFoundError:
                print(f"Info: Data file not found, skipping: {file_path}")
                buffers[key] = None

        res_map = {'low': 'Low', 'high': 'High', 'xlow': 'XLow', 'xhigh': 'XHigh'}

        for icon in self.icons:
            for res_key, folder_name in res_map.items():
                if buffers[res_key] is None:
                    continue
                
                for i, p in enumerate(icon.resolutions[res_key].pics):
                    if p.size == 0:
                        continue
                    
                    if p.offset + p.size > len(buffers[res_key]):
                        print(f"Warning: Invalid size/offset for {icon.key} in {folder_name}. Skipping.")
                        continue
                    
                    extracted_data = buffers[res_key][p.offset : p.offset + p.size]
                    output_file = os.path.join(working_directory, folder_name, f"{icon.key}_s{i}.png")
                    with open(output_file, 'wb') as f:
                        f.write(extracted_data)


def show_usage():
    """Prints the usage instructions for the script."""
    print("Usage:")
    print(f"  Extract icons: {sys.argv[0]} -e \"path\\to\\IconResources.idx\" \"WorkingDirectory\"")
    print(f"  Pack icons:    {sys.argv[0]} -p \"path\\to\\IconResources.idx\" \"WorkingDirectory\"")
    ###print("\nFor packing, place your modified 'Splash.png' in the 'High' and/or 'Low' subdirectories of your working directory.")

# Main execution logic
if __name__ == "__main__":
    working_directory = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "Work")
    index_file_path = ""
    packing = False

    args = sys.argv[1:]

    if len(args) >= 2 and (args[0] == "-e" or args[0] == "-p"):
        index_file_path = args[1]
        if len(args) >= 3:
            working_directory = args[2]
        packing = args[0] == "-p"
    else:
        show_usage()
        sys.exit(1)

    res = IconResources(index_file_path)
    print(f"Successfully loaded: {res.name}")

    if packing:
        print(f"Packing icons from '{working_directory}'...")
        res.pack(working_directory)
        print("Packing complete.")
    else:
        print(f"Extracting icons to '{working_directory}'...")
        res.extract(working_directory)
        print("Extraction complete.")
