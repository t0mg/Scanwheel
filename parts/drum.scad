nozzle_diameter = 0.2;

drum_diameter = 60;
drum_height = 12;

scan_lines = 20;
scan_height = 8;
interlaced_fields = 1;
clockwise = false;

slit_height = scan_height / scan_lines;
slit_width = slit_height * 0.75;

mass_height = 4.3;
mass_radius = 10;

spindle_diameter = 6.6;
spindle_bore = 1.5;

drum_radius = drum_diameter / 2;

smoothness = 360;

function line_index(line) =
    let(
        fields = max(1, interlaced_fields),
        field_lines = floor(scan_lines / fields),
        field_line = line % fields,
        carry = scan_lines % fields,
        offset = field_line * field_lines + min(field_line, carry)
    )
    offset + floor(line / fields);


module pinholes() {
    if (interlaced_fields > 1) {
        echo(str(scan_lines, " lines, ", interlaced_fields, " fields:"));
        for (i = [0 : scan_lines - 1]) {
            echo(str(i, ": ", line_index(i)));
        }
    }
    
    union() {
        for (i = [0 : scan_lines - 1]) {
            t = i / scan_lines;
            l = line_index(i);
            z = l / scan_lines;
            translate([0, 0, z * scan_height + (drum_height - scan_height) / 2 + slit_height / 2])
                rotate([0, 0, t * (clockwise ? -360 : 360)])
                    translate([drum_radius / 2, 0, 0])
                        cube([drum_radius, slit_width, slit_height], center=true);
        }
    }
}

module drum() {
    wall_limit = 0.4;

    difference() {
        translate([0,0,0])
            cylinder(h=drum_height, r=drum_radius, $fn=smoothness);

        union() {
            translate([0,0,-1])
                cylinder(h=drum_height, r=drum_radius - wall_limit, $fn=smoothness);
            
            translate([0,0,(drum_height - scan_height) / 2 - 0.5])
                cylinder(h=scan_height + 1, r=drum_radius - nozzle_diameter, $fn=smoothness);
            
            pinholes();
        }
    }
}

module mass() {
    translate([0,0,drum_height - mass_height])
        cylinder(h=mass_height, r=mass_radius, $fn=smoothness * mass_radius / drum_radius);
}

module spindle() {
    spindle_lift = 0.7;

    difference() {
        translate([0,0,spindle_lift])
            linear_extrude(height=drum_height-spindle_lift, scale=1.125)
                circle(r=spindle_diameter / 2, $fn=smoothness * spindle_diameter / drum_radius);
        
        union() {
            translate([0,0,0])
                cylinder(h=drum_height, r=spindle_bore / 2, $fn=30);
            
            for (i = [0 : 5]) {
                rotate([0, 0, i * 360 / 5])
                    translate([spindle_bore / 2, 0, 0])
                        cylinder(h=10, r=0.2, $fn=15);
            }
        }
    }
}

module section() {    
    translate([-drum_radius, 0, -1])
        cube([drum_diameter, drum_diameter, drum_height + 2]);
}


difference() {
    union() {
        drum();
        mass();
        spindle();
    }
    
    //section();
}
