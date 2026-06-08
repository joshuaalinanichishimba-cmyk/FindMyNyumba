# ── GET /admin/reports ───────────────────────────────────────────────────────
@router.get("/reports")
def get_reports(
    status_filter: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Report).order_by(Report.created_at.desc())
    if status_filter:
        q = q.filter(Report.status == status_filter)
    reports = q.all()

    # Batch-fetch names to avoid N+1
    reporter_ids = {r.reporter_id for r in reports}
    handler_ids  = {r.handled_by for r in reports if r.handled_by}
    listing_ids  = {r.listing_id for r in reports if r.listing_id}
    user_ids     = reporter_ids | handler_ids
    users        = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    listings     = {l.id: l for l in db.query(Listing).filter(Listing.id.in_(listing_ids)).all()} if listing_ids else {}

    return [
        {
            "id":             r.id,
            "listing_id":     r.listing_id,
            "listing_title":  listings[r.listing_id].title if r.listing_id and r.listing_id in listings else None,
            "reporter_id":    r.reporter_id,
            "reporter_name":  users[r.reporter_id].full_name if r.reporter_id in users else "Unknown",
            "reporter_email": users[r.reporter_id].email     if r.reporter_id in users else "",
            "reason":         r.reason,
            "description":    r.description,
            "status":         r.status,
            "resolution":     r.resolution,
            "handled_by":     r.handled_by,
            "handled_by_name": users[r.handled_by].full_name if r.handled_by and r.handled_by in users else None,
            "handled_at":     r.handled_at.isoformat() if r.handled_at else None,
            "created_at":     r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


# ── PATCH /admin/reports/{id}/investigate ────────────────────────────────────
@router.patch("/reports/{report_id}/investigate")
def investigate_report(report_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = "investigating"
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Report marked as investigating."}


# ── PATCH /admin/reports/{id}/resolve ────────────────────────────────────────
@router.patch("/reports/{report_id}/resolve")
def resolve_report(report_id: int, body: "ResolveBody", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = "resolved"
    report.resolution = body.resolution
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Report resolved."}


# ── PATCH /admin/reports/{id}/dismiss ────────────────────────────────────────
@router.patch("/reports/{report_id}/dismiss")
def dismiss_report(report_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = "dismissed"
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Report dismissed."}
