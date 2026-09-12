import type { WeightUnit } from "../contracts";

interface Props {
  weight: string;
  unit: WeightUnit;
  priority: number | null;
  errors: { weight?: string; priority?: string };
  disabled?: boolean;
  onWeightChange: (value: string) => void;
  onUnitChange: (unit: WeightUnit) => void;
  onPriorityChange: (priority: number) => void;
}

export function isStarFilled(star: number, priority: number | null): boolean {
  return priority !== null && star <= priority;
}

export function RequiredItemInputs(props: Props) {
  return (
    <>
      <div className="field-group">
        <label htmlFor="weight">Weight <span>Required</span></label>
        <div className="weight-row">
          <input id="weight" inputMode="decimal" type="number" min="0" step="any" value={props.weight}
            aria-invalid={Boolean(props.errors.weight)} aria-describedby={props.errors.weight ? "weight-error" : undefined}
            disabled={props.disabled} onChange={event => props.onWeightChange(event.target.value)} />
          <select aria-label="Weight unit" value={props.unit} disabled={props.disabled}
            onChange={event => props.onUnitChange(event.target.value as WeightUnit)}>
            <option value="g">g</option><option value="kg">kg</option><option value="oz">oz</option><option value="lb">lb</option>
          </select>
        </div>
        {props.errors.weight && <p id="weight-error" className="field-error">{props.errors.weight}</p>}
      </div>

      <fieldset className="field-group" disabled={props.disabled} aria-describedby={props.errors.priority ? "priority-error" : undefined}>
        <legend>Priority <span>Required</span></legend>
        <div className="stars">
          {[1, 2, 3, 4, 5].map(star => (
            <label key={star} className={isStarFilled(star, props.priority) ? "selected" : ""}>
              <input type="radio" name="priority" value={star} checked={props.priority === star}
                onChange={() => props.onPriorityChange(star)} />
              <b aria-hidden="true">★</b><span className="visually-hidden">{star} {star === 1 ? "star" : "stars"}</span>
            </label>
          ))}
        </div>
        {props.errors.priority && <p id="priority-error" className="field-error">{props.errors.priority}</p>}
      </fieldset>
    </>
  );
}
