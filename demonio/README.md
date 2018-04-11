Para demonizar el servidor de gnuhealth seguir los siguientes pasos:

Copiar el archivo start_gnuhealth.sh dentro de /home/gnuhealth/
Darle privilegios de ejecución al script (chmod +x start_gnuhealth.sh)
Copiar el archivo gnuhealth.service dentro de /lib/systemd/system

Para iniciar:
systemctl start gnuhealth

Para detener:
systemctl stop gnuhealth

Para que se ejecute en el inicio:
systemctl enable gnuhealth
