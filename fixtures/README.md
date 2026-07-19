# Fixtures

The Meridian Financial Group legacy estate: Blue Prism processes
authored in Blue Prism v7.5.1 and exported as real .bprelease files
(roadmap week 1).

| File | Contents |
|---|---|
| meridian-estate.bprelease | Full estate: 4 processes, 2 objects, 3 queues |
| meridian-p01-dispute-intake.bprelease | P01 + both objects + Q-Disputes |
| meridian-p03-address-change.bprelease | P03 + MFG Core Banking |
| meridian-p04-reconciliation.bprelease | P04 + both objects |
| meridian-p06-dispute-feeder.bprelease | P06 + Q-Disputes |

P01, P03, P04, and P06 were authored by hand; further processes (P02,
P05, P07, P08) will be derived by editing copies of this XML. These
files are parsed, never executed: the objects are stubs with
hard-coded outputs, and all companies, processes, and data are
fictional.
