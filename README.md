# Lora-Hakaton

Cuando cae la red celular, la coordinación se cae con ella. Este prototipo propone lo contrario: una red que se arma entre los propios nodos, sigue funcionando sin internet y permite ver dónde está cada uno.

La capa de radio no se construye desde cero: usamos **Meshtastic**, un proyecto open source de malla LoRa, para el descubrimiento, el reenvío de mensajes y la cobertura sin torres ni SIM. La innovación está en lo que construimos encima:

- un **mapa con localización GPS** de los nodos activos, para entender la cobertura de la red;
- un **servidor local de analítica** que recibe, organiza y consulta los mensajes de la malla;
- el dimensionamiento de un **kit de energía** (panel solar y/o eólico, en evaluación) para sostener la operación cuando falte el suministro eléctrico.

El resultado buscado no es solo que los nodos se hablen: es que esa información llegue a quien decide en el territorio, incluso cuando no hay señal.
