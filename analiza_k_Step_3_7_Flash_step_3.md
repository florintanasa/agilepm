# Analiză N:N în jmix_cli/user.py + jmix_cli/views.py vs documentația Jmix

## Cazuri de N:N conform documentației Jmix

Documentația structrează N:N pe **3 dimensiuni independente**:

### 1. Direcție
| Tip | Descriere | Exemplu doc |
|-----|-----------|-------------|
| **Unidirectional** | Navigabil doar de la o entitate la cealaltă | Veterinarian → Specialty |
| **Bidirectional** | Navigabil de la ambele puncte | Visit ↔ Specialty |

### 2. Ownership (pentru bidirectional)
| Tip | Descriere | Exemplu doc |
|-----|-----------|-------------|
| **Single Owning Side** | O singură entitate are @JoinTable, cealaltă are mappedBy | Visit ↣ Specialty |
| **Both Sides Owning** | Ambele au @JoinTable | Visit ↣↢ TreatmentRoom |

### 3. Mapping
| Tip | Descriere | Exemplu doc |
|-----|-----------|-------------|
| **Direct** | @ManyToMany + join table, fără entitate intermediară | Visit ⇄ Specialty |
| **Indirect** | Entitate intermediară cu 2× @ManyToOne (nu este chiar JPA N:N) | Pet ← InsuranceCoverage → InsuranceProvider |

---

## Ce este tratat în jmix_cli/user.py + jmix_cli/views.py

Codul acoperă **exact un singur caz**:

### ✅ Bidirectional N:N, Single Owning Side (sursa = owning)

**În user.py:**
- _inject_nn() (l. 56-79): injectează în User.java câmpul cu **@ManyToMany + @JoinTable** → User devine **owning side**
- _inject_inverse_for_relation() (l. 110-126): injectează în entitatea țintă câmpul **@ManyToMany(mappedBy = ...)** → target devine **non-owning side**

**În views.py:**
- gen_detail_view_from_csv() (l. 184-206): în detail view-ul **sursei** pune **multiSelectComboBoxPicker** (permite selecție multiplă, consistent cu owning side)
- inject_nn_grid_into_inverse_entity() (l. 455-503): în detail view-ul **țiiței** injectează un **dataGrid fără acțiuni** (doar citire, consistent cu non-owning side — UI nu poate persista modificări)

**Liquibase (liquibase.py l. 172-193):** creează join table {SRC}_{TGT}_LINK cu PK compus și 2 FK.

---

## Cazuri NEtratate (găuri)

| Caz | Unde lipsește |
|-----|---------------|
| **Unidirectional N:N** | _inject_inverse_for_relation() este apelat obligatoriu pentru N:N (l. 153 în user.py), deci nu există modul de a avea doar owning side fără mappedBy |
| **Both Sides Owning** | Codul folosește întotdeauna mappedBy pe target (l. 116 în user.py, l. 236 în entity.py); nu există nicio cale pentru a genera @JoinTable pe ambele părți |
| **Indirect Mapping (join entity)** | Nu este un tip de relație în CSV; ar necesita 2× N:1 + o entitate intermediară, complet afaria din scope-ul curent |

---

## Bug-uri observate în logica N:N

1. **Pluralizare incorectă** — user.py:111 și entity.py:230:
   inv_field_name = source_name.lower() + "s" if not source_name.endswith("s") else source_name.lower()
   Pentru Priority → generează prioritys în loc de priorities.

2. **Inversarea UI pentru N:N este disponibilă doar în build-all** — inject_nn_grid_into_inverse_entity() din views.py este apelată doar în cli.py:563 (fluxul build-all). Dacă se rulează ui-detail <Name> individual pentru o entitate țintă, grid-ul invers nu este injectat.

3. **Conflict potențial dacă ambele părți definesc relația în relations.csv** — Dacă există atât User,N:N,Priority,priorities cât și Priority,N:N,User,users, codul va încerca să injecteze inverse de două ori; idempotența se bazează pe string-match exact, dar logica de nume poate genera câmpuri duplicat cu nume diferite (prioritys vs priorities).

---

## Recomandare

Dacă dorești suport pentru toate cele 3 cazuri din documentație, ar trebui adăugată o coloană în relations.csv (ex. ownership=owning|inverse|both) și un flag pentru direction=unidirectional|bidirectional. Codul curent este hardcoded pe bidirectional + single owning (sursa owning).
