import { Resource } from '../context'
import { Cell } from './Field'

const NUM = ['float', 'monetary', 'integer']

export default function RecordTable({ res, records, columns, onOpen, order, onSort }: { res: Resource; records: any[]; columns?: string[]; onOpen: (r: any) => void; order?: string; onSort?: (f: string) => void }) {
  const cols = (columns || res.list).filter(c => res.fields[c])
  if (!records.length) return <div className="empty">Sin registros</div>
  const [oField, oDir] = (order || '').split(' ')
  // La columna de nombre (o la primera de texto) es la que se lee: recibe espacio prioritario; el resto se compacta.
  const cls = (c: string, i: number) => NUM.includes(res.fields[c].type) ? 'num' : (c === 'name' || (i === 0 && ['char', 'text'].includes(res.fields[c].type))) ? 'col-name' : ''
  return (
    <div className="table-wrap">
      <table className="list">
        <thead><tr>{cols.map((c, i) => <th key={c} className={cls(c, i)} onClick={() => onSort && onSort(c)}>{res.fields[c].string}{oField === c ? (oDir === 'desc' ? ' ▼' : ' ▲') : ''}</th>)}</tr></thead>
        <tbody>
          {records.map(r => (
            <tr key={r.id} className="row" onClick={() => onOpen(r)}>
              {cols.map((c, i) => <td key={c} className={cls(c, i)}><Cell f={res.fields[c]} v={r[c]} /></td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
