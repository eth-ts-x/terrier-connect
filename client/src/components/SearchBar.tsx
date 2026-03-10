import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  InputBase,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import { Search as SearchIcon } from "@mui/icons-material";
import { alpha, styled } from "@mui/material/styles";

const StyledSearch = styled("div")(({ theme }) => ({
  position: "relative",
  borderRadius: theme.shape.borderRadius,
  backgroundColor: alpha(theme.palette.common.white, 0.15),
  "&:hover": { backgroundColor: alpha(theme.palette.common.white, 0.25) },
  marginLeft: theme.spacing(1),
  width: "auto",
  display: "flex",
  alignItems: "center",
}));

export default function SearchBar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [type, setType] = useState<"keyword" | "tag">("keyword");

  const handleSearch = () => {
    if (!query.trim()) return;
    navigate(`/search?type=${type}&query=${encodeURIComponent(query.trim())}`);
  };

  return (
    <StyledSearch>
      <ToggleButtonGroup
        size="small"
        value={type}
        exclusive
        onChange={(_, v) => v && setType(v)}
        sx={{ mr: 0.5, "& .MuiToggleButton-root": { color: "inherit", borderColor: "rgba(255,255,255,0.3)", py: 0.3, px: 1, fontSize: "0.75rem" } }}
      >
        <ToggleButton value="keyword">Keyword</ToggleButton>
        <ToggleButton value="tag">Tag</ToggleButton>
      </ToggleButtonGroup>
      <InputBase
        placeholder="Search…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        sx={{ color: "inherit", ml: 1, flex: 1 }}
      />
      <IconButton size="small" color="inherit" onClick={handleSearch}>
        <SearchIcon />
      </IconButton>
    </StyledSearch>
  );
}
