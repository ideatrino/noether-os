#include <microkit.h>

void init(void)
{
    microkit_dbg_puts("ATTACKER|INFO: init running; I hold no channel to the server\n");
    microkit_dbg_puts("ATTACKER|INFO: now attempting to read the billing region directly...\n");

    volatile char *billing = (volatile char *)0x2000000;
    char stolen = billing[0];   /* NOT mapped into this PD -> the kernel faults here */
    (void) stolen;

    /* This line must NEVER print. If it does, confinement failed. */
    microkit_dbg_puts("ATTACKER|INFO: if you see this, confinement FAILED\n");
}

void notified(microkit_channel ch) { }
