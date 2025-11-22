import os
from astropy.io import fits
from datetime import datetime

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

def save_fits_data(data, savepath=None, header_text=None, serial=None):
    if data is None:
        return 
    if savepath is None:
        print("ERROR: No save path was provided. Saving data to current directory.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        savepath = dir_path + "/data"
    
    hdu = fits.PrimaryHDU(data)
    hdul = fits.HDUList([hdu])
    hdr = buildHeader(hdul=hdul, header=hdul[0].header, filename=None)
    curr_date = datetime.now().strftime("%Y_%m_%d__%H_%M_%S")
    
    filename = f"{savepath}/{curr_date}_{serial}.fits" if serial else f"{savepath}/{curr_date}.fits"
    hdul.writeto(filename, overwrite=True)

def save_csv_data(data, savepath=None, header_text=None):
    if data is None:
        return 
    if savepath is None:
        print("ERROR: No save path was provided. Saving data to current directory.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        savepath = dir_path + "/data/csv_data"
    
    import pandas as pd
    df = pd.DataFrame(data)
    curr_date = datetime.now().strftime("%Y_%m_%d__%H_%M_%S")
    
    df.to_csv(f"{savepath}/{curr_date}.csv", index=False)
    
    if header_text is not None:
        with open(f"{savepath}/{curr_date}--header.txt", 'w') as f:
            f.write(header_text)
                     
def save_xlsx_data(data, savepath=None, header_text=None):
    if data is None:
        return 
    if savepath is None:
        print("ERROR: No save path was provided. Saving data to current directory.")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        savepath = dir_path + "/data/xlsx_data"
    
    import pandas as pd
    df = pd.DataFrame(data)
    curr_date = datetime.now().strftime("%Y_%m_%d__%H_%M_%S")
    
    df.to_excel(f"{savepath}/{curr_date}.xlsx")
    
    if header_text is not None:
        with open(f"{savepath}/{curr_date}--header.txt", 'w') as f:
            f.write(header_text)