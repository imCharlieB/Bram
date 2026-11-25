"use strict";
// Passes microphone sound to the page. Runs only while the talk button is held.
registerProcessor("recorder", class extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0][0];
    if (channel) this.port.postMessage(channel.slice());
    return true;
  }
});
