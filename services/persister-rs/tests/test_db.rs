use persister_rs::db::build_batch_insert_query;

#[test]
fn test_build_batch_insert_query_single_row() {
    let sql = build_batch_insert_query(1);
    assert!(sql.starts_with("INSERT INTO meter_readings"));
    assert!(sql.contains("VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"));
    assert!(sql.ends_with("ON CONFLICT (meter_id, time) DO NOTHING;"));
}

#[test]
fn test_build_batch_insert_query_multiple_rows() {
    let sql = build_batch_insert_query(2);
    assert!(sql.contains("($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12), ($13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)"));
}

#[test]
fn test_build_batch_insert_query_empty() {
    let sql = build_batch_insert_query(0);
    assert_eq!(sql, "");
}
