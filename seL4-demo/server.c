#include <microkit.h>

/* 'billing' is mapped into THIS pd only, at the vaddr declared in the .system file. */
volatile char *billing = (volatile char *)0x2000000;

void init(void)
{
    microkit_dbg_puts("SERVER|INFO: init; I hold the billing region\n");
    billing[0] = 'B';                       /* write our own protected resource */
    microkit_dbg_puts("SERVER|INFO: wrote to billing successfully\n");
}

microkit_msginfo protected(microkit_channel ch, microkit_msginfo msginfo)
{
    /* The client never touches billing directly. It asks US, and we mediate
       using OUR capability. This is the deputy doing legitimate work. */
    char v = billing[0];
    billing[0] = v + 1;
    microkit_dbg_puts("SERVER|INFO: client request served; billing updated via server's capability\n");
    return microkit_msginfo_new(0, 0);
}

void notified(microkit_channel ch) { }
