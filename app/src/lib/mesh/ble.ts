// Transporte Bluetooth LE hacia un nodo Meshtastic.
// En Android usa el plugin nativo; en Chrome de escritorio usa Web Bluetooth
// (útil para probar con un nodo real desde el PC).
import { BleClient } from "@capacitor-community/bluetooth-le";
import type { ByteTransport } from "./protocol";

const SERVICE = "6ba1b218-15a8-461f-9fa8-5dcae273eafd";
const TO_RADIO = "f75c76d2-129e-4dad-a1dd-7866124401e7";
const FROM_RADIO = "2c55e69e-4993-11ed-b878-0242ac120002";
const FROM_NUM = "ed9da18c-a800-4f66-a670-aa7547e34453";

export class BleTransport implements ByteTransport {
  private deviceId?: string;
  private onBytes: (b: Uint8Array) => void = () => {};
  private reading = false;
  private again = false;
  private closing = false;

  async open(onBytes: (b: Uint8Array) => void, onClosed: (reason: string) => void): Promise<void> {
    this.onBytes = onBytes;
    this.closing = false;
    await BleClient.initialize({ androidNeverForLocation: true });
    // Muestra el selector del sistema filtrando solo nodos Meshtastic.
    const device = await BleClient.requestDevice({ services: [SERVICE] });
    this.deviceId = device.deviceId;
    await BleClient.connect(device.deviceId, () => {
      if (!this.closing) onClosed("se perdió la conexión Bluetooth");
    });
    // El nodo avisa por FROM_NUM cada vez que tiene datos nuevos para leer.
    await BleClient.startNotifications(device.deviceId, SERVICE, FROM_NUM, () => void this.drain());
    void this.drain();
  }

  async write(bytes: Uint8Array): Promise<void> {
    if (!this.deviceId) throw new Error("Bluetooth no conectado");
    await BleClient.write(this.deviceId, SERVICE, TO_RADIO,
                          new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength));
    void this.drain();
  }

  async close(): Promise<void> {
    this.closing = true;
    if (!this.deviceId) return;
    const id = this.deviceId;
    this.deviceId = undefined;
    try {
      await BleClient.stopNotifications(id, SERVICE, FROM_NUM);
    } catch { /* ya desconectado */ }
    try {
      await BleClient.disconnect(id);
    } catch { /* ya desconectado */ }
  }

  /** Lee FROM_RADIO hasta que el nodo devuelve un valor vacío. */
  private async drain(): Promise<void> {
    if (this.reading) {
      this.again = true;
      return;
    }
    this.reading = true;
    try {
      do {
        this.again = false;
        while (this.deviceId) {
          const view = await BleClient.read(this.deviceId, SERVICE, FROM_RADIO);
          if (view.byteLength === 0) break;
          this.onBytes(new Uint8Array(view.buffer, view.byteOffset, view.byteLength).slice());
        }
      } while (this.again && this.deviceId);
    } catch {
      /* la desconexión la reporta el callback de connect() */
    } finally {
      this.reading = false;
    }
  }
}
