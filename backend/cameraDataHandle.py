def buildFromTextFile(self, filename, header):
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

def buildHeader(self, hdul, header, filename = None, cameraConfig = None):
    if(filename is not None):
        self.buildFromTextFile(filename, header)
    else:
        header['SIMPLE'] = (True, "file conforms to FITS standard")
        header['BITPIX'] = (64, "number of bits per data pixel")
        header['READMODE'] = ('IMAGE   ', "Readout Mode")
        header['NAXIS'] = (2, 'number of array dimensions')
        header['NAXIS1'] = (1025, 'some number')
        header['NAXIS2'] = (1024, 'number 2')
        header['EXTEND'] = (True, '')

    return

def save_fits_data(self, data = None, savepath = None):
    if data is None:
        return 
    if savepath is None:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        savepath = f"{dir_path}/Camera_{self.serialNumber}"
    
    hdu = fits.PrimaryHDU(data)
    hdul = fits.HDUList([hdu])
    hdr = self.buildHeader(hdul=hdul, header=hdul[0].header, filename=None)
    hdul.writeto(f"{savepath}.fits", overwrite=True)


