// Menampilkan nama berkas yang dipilih dan mengunci tombol saat deteksi berjalan.
const input = document.getElementById("berkas");
const nama = document.getElementById("nama-berkas");
if (input && nama) {
  input.addEventListener("change", () => {
    const f = input.files[0];
    nama.textContent = f ? `${f.name} · ${(f.size / 1048576).toFixed(1)} MB`
                         : "Belum ada berkas dipilih";
  });
}

const form = document.getElementById("form-deteksi");
const tombol = document.getElementById("tombol-deteksi");
if (form && tombol) {
  form.addEventListener("submit", () => {
    tombol.textContent = "Memeriksa flow…";
    tombol.disabled = true;
  });
}