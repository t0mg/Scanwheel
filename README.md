# Scanwheel

Scanwheel is a drum style mechanical television you can build yourself.

![A closeup of Scanwheel displaying an image of a flower](./images/scanwheel01.jpg)

There's an accompanying [video](https://example.com/docs) showing the build process, with footage of it in action.

[![Scanwheel build video](./images/scanwheel02.jpg)](https://youtube.com)


## Parts

`Symbol Technologies 21-02485 stepper motor`
This still seems to be quite widely available online. It has an unusual wiring setup, but can be used
as a bipolar stepper motor by cutting the white wire before it goes into the 4 pin connector
as described [here](https://web.archive.org/web/20100520003941/http://www.picaxe.orconhosting.net.nz/stepdemo.jpg).

`A4988 based StepStick`
Something like the [Pololu 1182](https://www.pololu.com/product/1182).

`100uF Capacitor` across motor power & ground.

`Raspberry Pi Pico` Doesn't matter which, but use a Pico W if you want to stream wirelessly to the device.

`LEDs` In the design presented here there's a single RGB LED and 4 white LEDs, which seemed like a good
compromise between wiring complexity and image quality.

`Resistors` Each LED needs a current-limiting resistor. The R, G and B channels need to be matched in 
brightness to each other, and the overall RGB brightness needs to be matched to the white LEDs. Each LED
must individually draw no more than 12mA from the Pico, and all of them together must draw no more than
50mA. This means you need to determine the resistor values for the specific LEDs you have sourced -
measure the actual current drawn with your LED and resisor connected to 3.3V

I found that the red channel of the RGB LED was the deciding factor, drawing 10.75mA with a 120R resistor.
Matching that brightness meant 260R for green (2.9mA), 220R for blue (2.8mA) and 82R for white (4.6mA)


## Printing

There are three printed parts; the base, the drum and a lid.

The parts will fit best if they are scaled to compensate for shrinkage during printing - on my printer,
using PLA, I find that a scale of 100.33% in X and Y and 100% in Z achieves this.

The base and the lid don't need any special treatment, but the drum requires a bit of care in printing.
This part should be printed using the highest quality settings - small layer height and low speeds -
because small flaws in the pinholes are very visible in the final display.

The sides of the drum are a
single wall thick. In Orca Slicer this means you need to set 'Wall Generator' to 'Arachne'. The infill
should be 100%.

The [OpenSCAD](https://openscad.org/) model for the drum is included, allowing you modify the design.
One of the parameters is nozzle diameter, and if your printer has a 0.2mm nozzle I recommend using that
version. You might find you need to fit a washer over the drum's spindle to increase its moment of
inertia.


## Wiring

![Pictorial wiring diagram](./images/wiring.png)
