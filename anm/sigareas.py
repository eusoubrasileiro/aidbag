import re


# Ignorando sinal -S e -O latitude longitado consierando somente negativos
# o sinal é inserido somente no arquivo antes do ';'
reg = re.compile('\D*(\d{2})\D*(\d{2})\D*(\d{2})\D*(\d{3,})')
def fformatPoligonal(mlinestring, filename='CCOORDS.TXT', verbose=True):
    "formated file de poligonal para uso em SIGAREAS->Administrador->Inserir Poligonal"
    #reg.findall(string)[:3]
    fields = reg.findall(mlinestring)
    if len(fields)%2 != 0:
        print('Algo errado faltando campo em coordenada (lat. ou lon.)')
    else:
        with open(filename.upper(), 'w') as f: # must be CAPS otherwise system doesnt load
            for i in range(0,len(fields)-1, 2):
                lat = "-;{:03};{:02};{:02};{:03};-;".format(*list(map(int,fields[i])))
                lon = "{:03};{:02};{:02};{:03}".format(*list(map(int,fields[i+1])))
                f.write(lat+lon)
                f.write('\n')
                if verbose:
                    print(lat+lon)
    print("Output filename is: ", filename.upper())
