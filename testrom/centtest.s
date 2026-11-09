; license:CC0-1.0
; centtest.s - a test program for MAME's centiped driver, written for
; arcade-cabinet-simulator. It is not Atari code and uses no Atari data.
; testrom/build_testrom.py assembles it with asm6502.py, adds tile graphics,
; and writes the result under the centiped driver's ROM file names, so CI
; can run every fault primitive without a game ROM.
;
; What it does, so that each fault has something to break:
;   - boot: clears RAM, starts POKEY, sets the palette, checks that the XOR
;     of every program byte is zero (a flipped ROM bit fails this), then
;     draws a fixed playfield pattern and one motion object
;   - bad ROM: fills the playfield with tile $2A and stops
;   - main loop (free running, so its pass count follows the CPU clock):
;     counts passes, reads POKEY's random number into a 4-bin histogram and
;     onto playfield row 0, rewrites playfield cell $0590 every pass (as
;     the game does with some cells), and follows the trackball with
;     motion object 0
;   - IRQ: counts interrupts, kicks the watchdog and acknowledges, so a
;     lost interrupt lets the watchdog reset the board, as on the game

PLAYFIELD = $0400       ; 32 columns x 30 rows, $0400-$07BF
MO_PIC    = $07C0       ; motion object picture codes
MO_HPOS   = $07D0       ; motion object horizontal positions
MO_VPOS   = $07E0       ; motion object vertical positions
MO_COLOR  = $07F0       ; motion object colours
IN0       = $0C00       ; trackball: D7 direction, D0-D3 count
RANDOM    = $100A       ; POKEY random number
SKCTL     = $100F       ; POKEY serial/keyboard control
PAL_PF    = $1404       ; playfield colours 0-3 ($1404-$1407)
PAL_MO    = $140C       ; motion object colours 1-3 ($140D-$140F)
IRQACK    = $1800
WATCHDOG  = $2000       ; any write resets the watchdog

LOOPLO    = $10         ; main loop passes, 16 bits
LOOPHI    = $11
IRQLO     = $12         ; interrupts taken, 16 bits
IRQHI     = $13
RNGLAST   = $14         ; last random number read
TBLAST    = $15         ; last trackball count (low nibble)
TBPOS     = $16         ; trackball position, follows the motion
CKSUM     = $17         ; XOR of the program ROM, 0 when it's good
STATE     = $18         ; $00 running, $BA bad ROM
DELTA     = $19
PTR       = $1A         ; 2 bytes
RNGHIST   = $20         ; RANDOM & 3 counted in $20-$23
CELL      = $0590       ; rewritten every pass

        .org $2000
RESET:  SEI
        CLD
        LDX #$FF
        TXS
        STA WATCHDOG

        LDA #0          ; clear $0000-$03FF
        TAX
CLEAR:  STA $00,X
        STA $0100,X
        STA $0200,X
        STA $0300,X
        INX
        BNE CLEAR

        LDA #0          ; POKEY: hold in reset, then run with the random number generator on
        STA SKCTL
        LDA #3
        STA SKCTL

        LDA #$0F        ; palette: data bits are active low (bit 0 red, 1 green, 2 blue),
        STA PAL_PF      ; bit 3 high means full intensity. Black, red, green, white.
        LDA #$0E
        STA PAL_PF+1
        LDA #$0D
        STA PAL_PF+2
        LDA #$08
        STA PAL_PF+3
        LDA #$08
        STA PAL_MO+1
        STA PAL_MO+2
        STA PAL_MO+3

        LDA #<$2000     ; checksum: XOR of $2000-$3FFF
        STA PTR
        LDA #>$2000
        STA PTR+1
        LDY #0
        LDA #0
CKLOOP: EOR (PTR),Y
        INY
        BNE CKLOOP
        STA WATCHDOG
        INC PTR+1
        LDX PTR+1
        CPX #$40
        BNE CKLOOP
        STA CKSUM
        CMP #0
        BEQ ROMOK

BADROM: LDA #$BA
        STA STATE
        LDX #0
        LDA #$2A
BADFILL: STA PLAYFIELD,X
        STA PLAYFIELD+$100,X
        STA PLAYFIELD+$200,X
        STA PLAYFIELD+$2C0,X
        INX
        BNE BADFILL
HALT:   STA WATCHDOG
        JMP HALT

ROMOK:  LDX #0          ; playfield pattern: four pages of tile codes
PATTERN: TXA
        AND #$3F
        STA PLAYFIELD,X
        TXA
        EOR #$15
        AND #$3F
        STA PLAYFIELD+$100,X
        TXA
        EOR #$2A
        AND #$3F
        STA PLAYFIELD+$200,X
        TXA
        EOR #$33
        AND #$3F
        STA PLAYFIELD+$2C0,X
        INX
        BNE PATTERN

        LDA #$01        ; motion object 0 in the middle
        STA MO_PIC
        LDA #$80
        STA MO_HPOS
        STA TBPOS
        STA MO_VPOS
        LDA #0
        STA MO_COLOR
        LDA IN0
        AND #$0F
        STA TBLAST
        CLI

MAIN:   INC LOOPLO
        BNE M1
        INC LOOPHI
M1:     LDA RANDOM
        STA RNGLAST
        AND #3
        TAX
        INC RNGHIST,X
        LDA LOOPLO      ; show the random number on playfield row 0
        AND #$1F
        TAX
        LDA RNGLAST
        AND #$3F
        STA PLAYFIELD,X
        LDA #0          ; a cell the program writes on every pass
        STA CELL

        LDA IN0         ; trackball: the count moved by (new - old) mod 16,
        TAY             ; downwards when D7 is set
        AND #$0F
        SEC
        SBC TBLAST
        AND #$0F
        BEQ NOMOVE
        STA DELTA
        TYA
        BPL TBUP
        LDA #16
        SEC
        SBC DELTA
        STA DELTA
        LDA TBPOS
        SEC
        SBC DELTA
        JMP TBSET
TBUP:   LDA TBPOS
        CLC
        ADC DELTA
TBSET:  STA TBPOS
        STA MO_HPOS
NOMOVE: TYA
        AND #$0F
        STA TBLAST
        JMP MAIN

IRQ:    PHA
        INC IRQLO
        BNE I1
        INC IRQHI
I1:     STA WATCHDOG
        STA IRQACK
        PLA
        RTI

NMI:    RTI

CKFIX:  .byte 0         ; set by build_testrom.py so the XOR of the program is zero

        .org $3FFA
        .word NMI, RESET, IRQ
