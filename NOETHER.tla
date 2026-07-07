-------------------------------- MODULE NOETHER --------------------------------
(***************************************************************************)
(* An abstract capability system in the NOETHER style: subjects delegate    *)
(* authority ONLY via grant edges (the object-capability model).            *)
(*                                                                          *)
(* Safety property (Confinement): a designated Attacker never obtains any   *)
(* authority over a designated Secret object, under ANY sequence of         *)
(* delegations from a safe initial configuration. TLC verifies this by      *)
(* EXHAUSTIVELY exploring every reachable state - the jump from the sampled *)
(* property tests to bounded model checking.                                *)
(*                                                                          *)
(* Run:  java -cp tla2tools.jar tlc2.TLC NOETHER.tla                        *)
(***************************************************************************)
EXTENDS FiniteSets, Naturals

CONSTANTS Nucleus, Alice, Bob, Attacker, Secret, Pub

Subjects == {Nucleus, Alice, Bob, Attacker}
Objects  == {Secret, Pub}
Rights   == {"read", "write", "grant"}
Targets  == Objects \cup Subjects

Cap == [holder : Subjects, target : Targets, rights : SUBSET Rights]

VARIABLE holds

TypeOK == holds \subseteq Cap

(* Safe boot: Alice holds Secret but has NO grant edge to Attacker; Bob has *)
(* a grant edge to Attacker but no authority over Secret. No path exists,   *)
(* so no delegation sequence can carry Secret to Attacker.                  *)
InitialCaps ==
  { [holder |-> Alice, target |-> Secret,   rights |-> {"read", "write"}],
    [holder |-> Bob,   target |-> Attacker, rights |-> {"grant"}] }

Init == holds = InitialCaps

(* g delegates to r a capability (t, Rd): g must hold a grant edge to r and *)
(* must itself hold >= Rd over t (no amplification).                        *)
Grant(g, r, t, Rd) ==
  /\ \E c1 \in holds : c1.holder = g /\ c1.target = r /\ "grant" \in c1.rights
  /\ \E c2 \in holds : c2.holder = g /\ c2.target = t /\ Rd \subseteq c2.rights
  /\ holds' = holds \cup { [holder |-> r, target |-> t, rights |-> Rd] }

Next ==
  \E g \in Subjects, r \in Subjects, t \in Targets, Rd \in (SUBSET Rights) \ {{}} :
     Grant(g, r, t, Rd)

Spec == Init /\ [][Next]_holds

Confinement ==
  \A c \in holds : ~(c.holder = Attacker /\ c.target = Secret)

THEOREM Spec => [](TypeOK /\ Confinement)
================================================================================
