# monitor_azure.py
import time
import psutil
import subprocess


class MonitorAzure:
    def __init__(self):
        self.contador = 0
        self.inicio = time.time()

    def monitorear(self):
        """Monitorea el uso de Azure"""
        while True:
            time.sleep(5)
            elapsed = time.time() - self.inicio

            # Verificar procesos
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                if 'python' in proc.info['name']:
                    print(f"CPU: {proc.info['cpu_percent']}%")

            # Verificar red
            net = psutil.net_io_counters()
            print(f"Bytes enviados: {net.bytes_sent}")
            print(f"Bytes recibidos: {net.bytes_recv}")


if __name__ == "__main__":
    monitor = MonitorAzure()
    monitor.monitorear()