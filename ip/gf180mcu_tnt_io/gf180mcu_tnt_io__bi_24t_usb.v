(* blackbox *)
module gf180mcu_tnt_io__bi_24t_usb (CS, SL, IE, OE, PU, PD, A, PAD, Y, VDD, VSS, DVDD, DVSS);
    inout  VDD;
    inout  VSS;
    inout  DVDD;
    inout  DVSS;

    input	CS;
	input	SL;
	input	IE;
	input	OE;
	input	PU;
	input	PD;
	input	A;
	inout	PAD;
	output	Y;
endmodule
