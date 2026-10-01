import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title: 'Paid Growth, Measured', description: 'A clear workspace for agency operations and accountable campaign reporting.'};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
