import socket
from time import time, sleep
import struct
import threading
#from UR3e_rg2.dynamic_ur3e import UR3eRG2

IP = "10.172.18.74"
PUERTO = 30001

#visualizador = UR3eRG2()

def main() -> None:
    with socket.create_connection((IP,PUERTO)) as cliente:
        sleep(1)
        while True:
            pre_mensaje = cliente.recv(5)
            tam_mensaje, tipo_mensaje = struct.unpack(">iB",pre_mensaje)

            if(tipo_mensaje == 16):
                contador_bytes_subpaquete = 0
                tam_subpaquete = 5
                articulaciones = []
                while (contador_bytes_subpaquete<tam_mensaje):
                    pre_subpaquete = cliente.recv(5)
                    tam_subpaquete, tipo_subpaquete = struct.unpack(">iB",pre_subpaquete)
                    if(tipo_subpaquete==1):
                        for q in range(0,5):
                            articulacion = cliente.recv(41)
                            articulaciones.append(struct.unpack(">dddffffB",articulacion))#(q_actual,q_target, qd_actual, i_actual, v_actual, t_motor, t_micro, jointMode)
                            print(articulaciones[q][0])
                        print("\n")
                    else:
                        contador_bytes_subpaquete += tam_subpaquete#acumulo hasta que llego al final
            else:
                if(tam_mensaje>=5):
                    datos = cliente.recv(tam_mensaje-5)#descarto el mensaje


            pass

if __name__=="__main__":
    main()