const divColor = "black";

export function getDivColor() {
  return divColor;
}
export const teamColor = "#ff66c4";
export const iconColor = teamColor;

const cardStyle = {
  backgroundColor: divColor,
  borderRadius: "12px",
  padding: "20px",
  display: "flex",
  flexDirection: "column",
  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
  overflow: "auto", // scroll if contents overflow
  maxHeight: "100vh",
  color: teamColor,
};

export const iconSize = 16;

export const styles = {
  card: cardStyle,
  placeholderCard: {
    ...cardStyle,
    flexGrow: 1,
    flexShrink: 1,
    maxWidth: "100%",
  },
  section: {
    marginBottom: "20px",
  },
  scrollContainer: {
    overflowX: "auto",
    width: "100%",
  },
  table: {
    minWidth: "600px",
    borderSpacing: 0,
    borderCollapse: "collapse",
    textAlign: "center",
    fontSize: "20px",
    tableLayout: "fixed", // Important for equal width columns
    width: "100%", // Expand to container width
  },
  th: {
    border: "1px solid #ccc",
    padding: "8px",
    fontWeight: "bold",
    textDecoration: "underline",
    whiteSpace: "nowrap",
    // remove width
  },
  td: {
    border: "1px solid #ccc",
    padding: "8px",
    whiteSpace: "nowrap",
    // remove width
  },
};
