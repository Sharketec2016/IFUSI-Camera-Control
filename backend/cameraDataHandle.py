import os
from astropy.io import fits

def Header_from_text(header_text, header):
    x = 0
    for line in header_text.readlines():
        try:
            line = line.replace("\n", "")
            key = line.split("=")[0]
            value = line.split("=")[1]
        
            try:
                comment = line.split("/")[1]
            except:
                comment = ""
            
            value = value.split("/")[0].replace("'", "")
            
            
            try:
                value = int(float(value))
            except:
                pass
            
            try:
                value = value.replace("'", "")
            except:
                pass

            try:
                value = value.replace('"', "")
            except:
                pass
            
            try:
                if(('T' in value) and (len(value.replace(" ", "")) < 2)):
                    value = True
                elif('F' in value) and (len(value.replace(" ", "")) < 2):
                    value = False
                else:
                    pass
            except:
                pass
            
            header[key] = (value, comment)
            
            x+=1
            
            
            
        except Exception as e:
            print(f"Error: {e} and at line {x} in {header_text}")
            continue

def buildFromTextFile(filename, header):
    with open(filename, 'r') as f:
        Header_from_text(f, header)

def buildHeader(hdul, header, filename = None, header_text = None):
    if(filename is not None):
        buildFromTextFile(filename, header)
    else:
        Header_from_text(header_text, header)

    return

def save_fits_data(data, savepath=None, header_text=None):
    if data is None:
        return 
    if savepath is None:
        print("ERROR: No save path was provided. Saving data to current directory.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        savepath = dir_path + "/data"
    
    hdu = fits.PrimaryHDU(data)
    hdul = fits.HDUList([hdu])
    hdr = buildHeader(hdul=hdul, header=hdul[0].header, filename=None)
    hdul.writeto(f"{savepath}.fits", overwrite=True)


