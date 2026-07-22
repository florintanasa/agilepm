# Propunere: extindere CSV columns pentru N:N

## Header nou pentru relations.csv

source_entity,relation_type,target_entity,field_name,mandatory,direction,ownership

---

## Valorile posibile

- direction: unidirectional | bidirectional
- ownership: owning | inverse | both-owning

---

## Comportament propus pe UI/Java

- unidirectional + owning: doar sursa primește UI editabil; targetul nu primește nimic (fără mappedBy)
- bidirectional + single-owning: sursa primește multiSelectComboBoxPicker editabil; targetul primește dataGrid readonly
- bidirectional + both-owning: ambele primește multiSelectComboBoxPicker editabil + dataGrid cu acțiuni
