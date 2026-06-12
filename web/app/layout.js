export const metadata = {
  title: "Alpha Terminal",
  description: "On-chain intelligence suite",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body style={{ margin: 0, padding: 0, background: "#080808" }}>
        {children}
      </body>
    </html>
  );
}
