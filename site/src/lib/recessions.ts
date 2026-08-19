/** NBER business-cycle contractions, peak month to trough month.
 *
 * The paper's own figures shade these; keeping them here lets every chart on the
 * site read against the same reference. Public-domain reference dates from the
 * NBER Business Cycle Dating Committee.
 */
export const NBER_RECESSIONS: { peak: number; trough: number }[] = [
  { peak: 195708, trough: 195804 },
  { peak: 196004, trough: 196102 },
  { peak: 196912, trough: 197011 },
  { peak: 197311, trough: 197503 },
  { peak: 198001, trough: 198007 },
  { peak: 198107, trough: 198211 },
  { peak: 199007, trough: 199103 },
  { peak: 200103, trough: 200111 },
  { peak: 200712, trough: 200906 },
  { peak: 202002, trough: 202004 },
];
