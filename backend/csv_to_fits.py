import astropy
import pandas as pd
from astropy.table import Table
from astropy.io import fits
import os


def buildFromTextFile(filename, header):
    with open(filename, 'r') as f:
        x = 0
        for line in f.readlines():
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
                print(f"Error: {e} and at line {x} in {filename}")
                continue
    print(header.keys)            

def buildHeader(hdul, header, filename = None, cameraConfig = None):
    if(filename is not None):
        buildFromTextFile(filename, header)
    else:
        header['SIMPLE'] = (True, "file conforms to FITS standard")
        header['BITPIX'] = (64, "number of bits per data pixel")
        header['READMODE'] = ('IMAGE   ', "Readout Mode")
        header['NAXIS'] = (2, 'number of array dimensions')
        header['NAXIS1'] = (1025, 'some number')
        header['NAXIS2'] = (1024, 'number 2')
        header['EXTEND'] = (True, '')

    return

def convertData(source_path=None, save_path=None, df=None):


    if((source_path is not None) and (df is None)):

        df = None
        for file in os.listdir(source_path):
            filename = file.rsplit(".", 1)[0]
            extension = file.rsplit(".", 1)[1]
            if "xlsx" in extension:
                df = pd.read_excel(f"{source_path}/{filename}.xlsx")
            elif "csv" in extension:
                df = pd.read_csv(f"{source_path}/{filename}.csv")
            else:
                print("Error, something went wrong")
                return None
            hdu = fits.PrimaryHDU(data=df.to_numpy())
            hdul = fits.HDUList([hdu])
            buildHeader(hdul, hdul[0].header, r"/home/matt/Documents/Southern_Graduate_Work/Astro /Python Coding/exmapleHeader.txt")
            savestring  = f"{save_path}/{filename}.fits"
            hdul.writeto(savestring, overwrite=True)
    elif not df is None:

        hdu = fits.PrimaryHDU(data=df.to_numpy())
        hdul = fits.HDUList([hdu])
        # buildHeader(hdul, hdul[0].header)

        # hdul.writeto(f"{save_path}\{filename}.fits", overwrite=True)
        return hdul


if __name__ == '__main__':
    source_path = r"/home/matt/Documents/Southern_Graduate_Work/Astro /Python Coding/Data/CSV_Data"
    save_path = r"/home/matt/Documents/Southern_Graduate_Work/Astro /Python Coding/Data/FITS_Data"
    convertData(source_path, save_path)