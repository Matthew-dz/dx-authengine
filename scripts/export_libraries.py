import importlib.metadata as md

def export_libraries():
    dists = sorted(md.distributions(), key=lambda d: d.metadata['Name'].lower())

    lines = []
    lines.append("====================================================================================================")
    lines.append("DANH SÁCH TẤT CẢ CÁC THƯ VIỆN ĐÃ CÀI ĐẶT TRONG DỰ ÁN DX-AUTHENGINE (venv/Lib/site-packages)")
    lines.append("====================================================================================================")
    lines.append(f"Tổng số lượng thư viện đã cài đặt: {len(dists)}")
    lines.append("")
    lines.append(f"{'STT':<4} | {'TÊN THƯ VIỆN':<36} | {'PHIÊN BẢN':<12} | {'GIẤY PHÉP':<22} | MÔ TẢ TÓM TẮT")
    lines.append("-" * 120)

    for idx, d in enumerate(dists, 1):
        name = d.metadata['Name']
        ver = d.version
        lic = d.metadata.get('License') or ''
        if not lic or '\n' in lic or len(lic) > 25:
            classifiers = [c.split('::')[-1].strip() for c in d.metadata.get_all('Classifier') or [] if 'License' in c]
            lic = classifiers[0] if classifiers else (lic.split('\n')[0][:22] if lic else 'Open Source')
        summary = (d.metadata.get('Summary') or '').replace('\n', ' ').strip()
        if len(summary) > 60:
            summary = summary[:57] + '...'
        lines.append(f"{idx:<4} | {name:<36} | {ver:<12} | {lic:<22} | {summary}")

    lines.append("")
    lines.append("====================================================================================================")
    lines.append("DANH SÁCH DẠNG REQUIREMENTS (NAME==VERSION)")
    lines.append("====================================================================================================")
    for d in dists:
        lines.append(f"{d.metadata['Name']}=={d.version}")

    output_path = "libraries_list.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Đã xuất thành công {len(dists)} thư viện vào file: {output_path}")

if __name__ == "__main__":
    export_libraries()
