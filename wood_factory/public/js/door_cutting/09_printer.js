// =====================================================
// Print Cutting Plan
// Door Cutting Order - Phase 1 Split File
// =====================================================

(() => {
    const DCO = window.DCO = window.DCO || {};
    const { escape_html } = DCO;

    // طباعة خطة القص على ورقة A4 Portrait
    function print_cutting_plan(frm) {
        const plan_html = frm.doc.cutting_plan_html || "";

        if (!plan_html) {
            frappe.msgprint("لا يوجد مخطط قص للطباعة. اضغط أولًا على إعادة حساب خطة القص.");
            return;
        }

        const title = "خطة قص - " + (frm.doc.name || "");
        const print_window = window.open("", "_blank");

        if (!print_window) {
            frappe.msgprint("المتصفح منع فتح نافذة الطباعة. اسمح بالنوافذ المنبثقة ثم جرّب مرة أخرى.");
            return;
        }

        print_window.document.open();

        print_window.document.write(`
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
                <head>
                    <meta charset="UTF-8">
                    <title>${escape_html(title)}</title>

                    <style>
                        @page {
                            size: A4 portrait;
                            margin: 6mm;
                        }

                        * {
                            -webkit-print-color-adjust: exact !important;
                            print-color-adjust: exact !important;
                            box-sizing: border-box !important;
                        }

                        html,
                        body {
                            margin: 0;
                            padding: 0;
                            background: #ffffff !important;
                            color: #111111 !important;
                            font-family: Arial, Tahoma, sans-serif;
                            direction: rtl;
                        }

                        body {
                            padding: 5mm;
                        }

                        .print-header {
                            display: flex;
                            justify-content: space-between;
                            align-items: flex-start;
                            border-bottom: 2px solid #111;
                            padding-bottom: 5px;
                            margin-bottom: 6px;
                            page-break-after: avoid;
                        }

                        .print-title {
                            font-size: 18px;
                            font-weight: bold;
                            margin-bottom: 4px;
                        }

                        .print-info {
                            font-size: 10px;
                            line-height: 1.5;
                        }

                        .print-info-ltr {
                            direction: ltr;
                            text-align: left;
                        }

                        .dco-cutting-plan {
                            color: #111 !important;
                            background: #fff !important;
                            padding: 0 !important;
                            margin: 0 !important;
                            border-radius: 0 !important;
                            font-family: Arial, Tahoma, sans-serif !important;
                            font-size: 10px !important;
                        }

                        .dco-cutting-plan h2 {
                            display: none !important;
                        }

                        .dco-cutting-plan > div:first-of-type {
                            font-size: 10px !important;
                            line-height: 1.35 !important;
                            margin-bottom: 4px !important;
                        }

                        .dco-summary-grid {
                            display: grid !important;
                            grid-template-columns: repeat(4, 1fr) !important;
                            gap: 4px !important;
                            margin: 4px 0 6px 0 !important;
                        }

                        .dco-summary-card {
                            border: 1px solid #aaa !important;
                            border-radius: 4px !important;
                            padding: 4px !important;
                            background: #f8f8f8 !important;
                            font-size: 9px !important;
                        }

                        .dco-summary-card b {
                            display: block !important;
                            font-size: 8px !important;
                            color: #444 !important;
                            margin-bottom: 2px !important;
                        }

                        .dco-summary-card span {
                            font-size: 11px !important;
                            font-weight: bold !important;
                            color: #111 !important;
                        }

                        .dco-sheet-card {
                            border: 1px solid #777 !important;
                            border-radius: 5px !important;
                            padding: 5px !important;
                            margin: 7px 0 0 0 !important;
                            background: #fff !important;
                            page-break-inside: avoid !important;
                            break-inside: avoid !important;

                            /*
                                مهم:
                                هذا يصغّر اللوح والجدول ليتناسبا مع A4 Portrait.
                                إذا أردته أكبر قليلًا اجعلها 0.72
                                إذا بقي مقطوعًا اجعلها 0.62
                            */
                            zoom: 0.68;
                        }

                        .dco-sheet-card + .dco-sheet-card {
                            page-break-before: always !important;
                            break-before: page !important;
                        }

                        .dco-sheet-title {
                            display: flex !important;
                            justify-content: space-between !important;
                            align-items: center !important;
                            font-size: 11px !important;
                            font-weight: bold !important;
                            margin-bottom: 4px !important;
                        }

                        .dco-sheet-board {
                            border: 2px solid #111 !important;
                            background:
                                linear-gradient(90deg, rgba(0,0,0,0.05) 1px, transparent 1px),
                                linear-gradient(rgba(0,0,0,0.05) 1px, transparent 1px),
                                #ffffff !important;
                            background-size: 32px 32px !important;
                            overflow: hidden !important;
                            direction: ltr !important;
                            margin: 0 auto 5px auto !important;
                        }

                        .dco-piece {
                            border: 1px solid #111 !important;
                            background: #e4f5ff !important;
                            color: #111 !important;
                            font-size: 8px !important;
                            line-height: 1.1 !important;
                            padding: 1px !important;
                        }

                        .dco-piece b {
                            font-size: 8px !important;
                            font-weight: bold !important;
                        }

                        .dco-piece span,
                        .dco-piece small {
                            font-size: 7px !important;
                        }

                        .dco-table {
                            width: 100% !important;
                            border-collapse: collapse !important;
                            margin-top: 4px !important;
                            font-size: 8px !important;
                        }

                        .dco-table th,
                        .dco-table td {
                            border: 1px solid #777 !important;
                            padding: 2px 3px !important;
                            text-align: center !important;
                            line-height: 1.15 !important;
                            white-space: nowrap !important;
                        }

                        .dco-table th {
                            background: #eeeeee !important;
                            font-weight: bold !important;
                        }

                        @media print {
                            .no-print {
                                display: none !important;
                            }

                            a[href]:after {
                                content: "" !important;
                            }
                        }
                    </style>
                </head>

                <body>
                    <div class="print-header">
                        <div>
                            <div class="print-title">خطة قص</div>
                            <div class="print-info">
                                رقم الطلب: ${escape_html(frm.doc.name || "")}<br>
                                الزبون: ${escape_html(frm.doc.customer || "")}<br>
                                نوع اللوح:
                                <span dir="ltr">${escape_html(frm.doc.board_item || "")}</span>
                            </div>
                        </div>

                        <div class="print-info print-info-ltr">
                            ${frappe.datetime.now_datetime()}<br>
                            ERPNext Cutting Plan
                        </div>
                    </div>

                    ${plan_html}

                    <script>
                        window.onload = function () {
                            setTimeout(function () {
                                window.focus();
                                window.print();
                            }, 700);
                        };
                    <\/script>
                </body>
            </html>
        `);

        print_window.document.close();
    }

    // نهاية دالة الطباعة

    Object.assign(DCO, {
        print_cutting_plan
    });
})();
